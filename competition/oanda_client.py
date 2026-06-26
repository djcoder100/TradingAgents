# competition/oanda_client.py
"""OANDA broker adapter (REST API).

OANDA is perfect for Forex and metals trading (EURUSD, XAUUSD, etc.)
with 50:1 leverage and works beautifully on macOS.

This adapter implements AbstractBrokerClient for seamless engine integration.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Dict, List
import requests
from urllib.parse import urljoin

from competition.api_client import AbstractBrokerClient
from competition.models import (
    AccountState,
    RegulatedOrder,
    Position,
    OrderResult,
    OrderAction,
    ApprovalStatus,
)
from competition.oanda_config import (
    OANDA_API_KEY,
    OANDA_ACCOUNT_ID,
    OANDA_BASE_URL,
    OANDA_ENVIRONMENT,
    OANDA_SYMBOL_OVERRIDES,
    OANDA_DEFAULT_SYMBOLS,
    REQUEST_TIMEOUT_S,
    DEFAULT_LEVERAGE,
)

logger = logging.getLogger(__name__)


class OANDAClient(AbstractBrokerClient):
    """OANDA REST API broker client.

    Ideal for Forex and metals trading. Works on macOS, Linux, Windows.
    Supports paper and live trading with 50:1 leverage.
    """

    def __init__(self):
        """Initialize OANDA client."""
        if not OANDA_API_KEY or not OANDA_ACCOUNT_ID:
            raise ValueError(
                "OANDA credentials missing. Set OANDA_API_KEY and OANDA_ACCOUNT_ID env vars. "
                "Get them from https://www.oanda.com/account/ → Manage Account → API Access"
            )

        self._api_key = OANDA_API_KEY
        self._account_id = OANDA_ACCOUNT_ID
        self._base_url = OANDA_BASE_URL
        self._session = requests.Session()
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        self._connected = False
        self._last_health_check = 0
        self._orders: Dict[str, OrderResult] = {}

        logger.info(
            "OANDAClient initializing — account=%s, environment=%s, endpoint=%s",
            self._account_id,
            OANDA_ENVIRONMENT,
            self._base_url,
        )

        # Verify connection
        if not self.reconnect():
            raise ConnectionError("Failed to connect to OANDA")

        logger.info("✓ Connected to OANDA")

    # ======================================================================
    # Connection Management
    # ======================================================================

    def is_connected(self) -> bool:
        """Check if connected to OANDA."""
        if not self._connected:
            return False

        # Periodic health check every 30s
        now = time.time()
        if now - self._last_health_check > 30:
            try:
                account = self._request("GET", f"/v3/accounts/{self._account_id}")
                self._last_health_check = now
                if account:
                    return True
            except Exception as e:
                logger.warning("OANDA health check failed: %s", e)
                self._connected = False
                return False

        return True

    def reconnect(self) -> bool:
        """Reconnect to OANDA."""
        try:
            # Test connection by fetching account info
            response = self._request("GET", f"/v3/accounts/{self._account_id}")
            if response is None or "account" not in response:
                logger.error("Failed to fetch account info from OANDA")
                self._connected = False
                return False

            account = response["account"]
            logger.info(
                "✓ Connected to OANDA: %s (balance=$%.2f, equity=$%.2f, leverage=1:%d)",
                account.get("alias", "Account"),
                float(account.get("balance", 0)),
                float(account.get("equity", 0)),
                int(account.get("marginRate", 0.02) ** -1) if float(account.get("marginRate", 0.02)) > 0 else 50,
            )
            self._connected = True
            self._last_health_check = time.time()
            return True

        except Exception as e:
            logger.error("OANDA reconnect failed: %s", e)
            self._connected = False
            return False

    # ======================================================================
    # Core Broker API
    # ======================================================================

    def get_account_state(self) -> AccountState:
        """Return current account state."""
        return self.call_with_retry(self._oanda_get_account_state)

    def _oanda_get_account_state(self) -> AccountState:
        """Fetch account state from OANDA."""
        try:
            response = self._request("GET", f"/v3/accounts/{self._account_id}")
            if response is None or "account" not in response:
                raise ConnectionError("account info returned None")

            account = response["account"]

            # Calculate leverage
            margin_rate = float(account.get("marginRate", 0.02))
            leverage = int(margin_rate ** -1) if margin_rate > 0 else 50

            return AccountState(
                balance=float(account.get("balance", 0)),
                equity=float(account.get("equity", 0)),
                margin_used=float(account.get("marginUsed", 0)),
                margin_free=float(account.get("marginAvailable", 0)),
                margin_level=100.0 * float(account.get("equity", 0)) / max(float(account.get("marginUsed", 1)), 1),
                leverage=leverage,
                open_positions_count=int(account.get("openPositionCount", 0)),
                open_orders_count=int(account.get("openTradeCount", 0)),
                currency="USD",
            )
        except Exception as e:
            logger.error("Failed to fetch account state: %s", e)
            raise

    def get_positions(self) -> list[Position]:
        """Return all open positions."""
        return self.call_with_retry(self._oanda_get_positions)

    def _oanda_get_positions(self) -> list[Position]:
        """Fetch open positions from OANDA."""
        try:
            response = self._request("GET", f"/v3/accounts/{self._account_id}/openPositions")
            if response is None or "positions" not in response:
                return []

            positions = []
            for pos in response["positions"]:
                # OANDA returns long and short side separately
                for side, trades in [("long", pos.get("long", {})), ("short", pos.get("short", {}))]:
                    units = float(trades.get("units", 0))
                    if units == 0:
                        continue

                    # Map OANDA symbol back to engine ticker
                    oanda_symbol = pos["instrument"]
                    engine_ticker = self._oanda_to_engine(oanda_symbol)

                    position = Position(
                        ticker=engine_ticker,
                        direction="BUY" if units > 0 else "SELL",
                        size=abs(units),
                        entry_price=float(trades.get("averagePrice", 0)),
                        current_price=float(pos.get("price", 0)),
                        unrealized_pnl=float(trades.get("unrealizedPL", 0)),
                        timestamp=int(time.time()),
                    )
                    positions.append(position)

            return positions
        except Exception as e:
            logger.error("Failed to fetch positions: %s", e)
            raise

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Return bid/ask midpoint for each ticker."""
        return self.call_with_retry(self._oanda_get_prices, tickers)

    def _oanda_get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Fetch prices from OANDA."""
        prices = {}
        try:
            # Build instruments parameter
            oanda_symbols = [self._engine_to_oanda(t) for t in tickers]
            instruments = ",".join(oanda_symbols)

            response = self._request(
                "GET",
                f"/v3/accounts/{self._account_id}/pricing",
                params={"instruments": instruments},
            )

            if response is None or "prices" not in response:
                logger.warning("No pricing data from OANDA")
                return {t: None for t in tickers}

            # Map prices back to engine tickers
            for price_data in response["prices"]:
                oanda_symbol = price_data["instrument"]
                engine_ticker = self._oanda_to_engine(oanda_symbol)

                bid = float(price_data.get("bids", [{}])[0].get("price", 0))
                ask = float(price_data.get("asks", [{}])[0].get("price", 0))

                if bid > 0 and ask > 0:
                    mid = (bid + ask) / 2.0
                    prices[engine_ticker] = mid
                else:
                    prices[engine_ticker] = None

            # Fill in any missing tickers with None
            for ticker in tickers:
                if ticker not in prices:
                    prices[ticker] = None

            return prices
        except Exception as e:
            logger.error("Failed to fetch prices: %s", e)
            raise

    def place_order(self, order: RegulatedOrder) -> OrderResult:
        """Submit a regulated order to OANDA."""
        return self.call_with_retry(self._oanda_place_order, order)

    def _oanda_place_order(self, order: RegulatedOrder) -> OrderResult:
        """Execute order placement on OANDA."""
        try:
            oanda_symbol = self._engine_to_oanda(order.ticker)

            # Convert notional to units (need price first)
            price_response = self._request(
                "GET",
                f"/v3/accounts/{self._account_id}/pricing",
                params={"instruments": oanda_symbol},
            )

            if price_response is None or not price_response.get("prices"):
                raise ValueError(f"Cannot get price for {order.ticker}")

            current_price = float(price_response["prices"][0]["bids"][0]["price"])
            units = order.order_size_notional / current_price

            # OANDA order request
            order_type = "MARKET" if order.order_type == "MARKET" else "LIMIT"
            request_data = {
                "order": {
                    "instrument": oanda_symbol,
                    "units": units if order.action == OrderAction.BUY else -units,
                    "type": order_type,
                    "timeInForce": "GTC",  # Good-Till-Cancelled
                }
            }

            # Add stop loss and take profit if provided
            if order.stop_loss:
                request_data["order"]["stopLossOnFill"] = {
                    "price": str(order.stop_loss),
                }
            if order.take_profit:
                request_data["order"]["takeProfitOnFill"] = {
                    "price": str(order.take_profit),
                }

            # Add limit price if specified
            if order_type == "LIMIT" and order.limit_price:
                request_data["order"]["priceBound"] = str(order.limit_price)

            logger.info(
                "Placing %s order: %s %s %.2f lots (notional: $%.0f)",
                order_type,
                order.action.value.upper(),
                oanda_symbol,
                units,
                order.order_size_notional,
            )

            response = self._request(
                "POST",
                f"/v3/accounts/{self._account_id}/orders",
                data=request_data,
            )

            if response is None:
                error_msg = "OANDA order placement returned None"
                logger.error(error_msg)
                return OrderResult(
                    order_id=None,
                    status=ApprovalStatus.REJECTED,
                    reason=error_msg,
                    filled_price=None,
                    filled_size=0,
                    timestamp=time.time(),
                )

            # Check response for trade/order
            if "orderFillTransaction" in response:
                # Market order filled immediately
                txn = response["orderFillTransaction"]
                return OrderResult(
                    order_id=txn["orderID"],
                    status=ApprovalStatus.FILLED,
                    filled_price=float(txn["price"]),
                    filled_size=abs(float(txn["units"])),
                    timestamp=time.time(),
                )
            elif "orderCreateTransaction" in response:
                # Pending order
                txn = response["orderCreateTransaction"]
                order_id = txn["orderID"]
                order_result = OrderResult(
                    order_id=order_id,
                    status=ApprovalStatus.PENDING,
                    reason=f"Order pending: type={order_type}",
                    timestamp=time.time(),
                )

                logger.info("✓ Order placed: %s (order_id=%s)", oanda_symbol, order_id)
                return order_result
            else:
                logger.warning("Unexpected OANDA response: %s", response)
                return OrderResult(
                    order_id=None,
                    status=ApprovalStatus.REJECTED,
                    reason="Unexpected response format",
                    timestamp=time.time(),
                )

        except Exception as e:
            logger.error("Failed to place order on OANDA: %s", e)
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        return self.call_with_retry(self._oanda_cancel_order, order_id)

    def _oanda_cancel_order(self, order_id: str) -> bool:
        """Execute order cancellation on OANDA."""
        try:
            response = self._request(
                "PUT",
                f"/v3/accounts/{self._account_id}/orders/{order_id}/cancel",
            )

            if response and "orderCancelTransaction" in response:
                logger.info("✓ Order %s cancelled", order_id)
                return True
            else:
                logger.error("Failed to cancel order %s: %s", order_id, response)
                return False
        except Exception as e:
            logger.error("Error cancelling order %s: %s", order_id, e)
            return False

    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """Get the status of a previously placed order."""
        try:
            response = self._request(
                "GET",
                f"/v3/accounts/{self._account_id}/orders/{order_id}",
            )

            if response is None or "order" not in response:
                return None

            order = response["order"]
            status_str = order.get("state", "PENDING")

            status_map = {
                "PENDING": ApprovalStatus.PENDING,
                "FILLED": ApprovalStatus.FILLED,
                "CANCELLED": ApprovalStatus.REJECTED,
                "EXPIRED": ApprovalStatus.REJECTED,
            }

            return OrderResult(
                order_id=order_id,
                status=status_map.get(status_str, ApprovalStatus.PENDING),
                filled_price=float(order.get("price", 0)) or None,
                filled_size=0,  # OANDA doesn't track filled size in order object
                timestamp=time.time(),
            )
        except Exception as e:
            logger.error("Failed to get order status for %s: %s", order_id, e)
            return None

    # ======================================================================
    # Internal Helpers
    # ======================================================================

    def _engine_to_oanda(self, engine_ticker: str) -> str:
        """Translate engine ticker to OANDA symbol (with underscore)."""
        # 1. Check explicit overrides
        if engine_ticker in OANDA_SYMBOL_OVERRIDES:
            return OANDA_SYMBOL_OVERRIDES[engine_ticker]

        # 2. Check default mapping
        if engine_ticker in OANDA_DEFAULT_SYMBOLS:
            return OANDA_DEFAULT_SYMBOLS[engine_ticker]

        # 3. Fallback: try adding underscore (e.g., EURUSD → EUR_USD)
        if len(engine_ticker) == 6 and engine_ticker.isupper():
            return f"{engine_ticker[:3]}_{engine_ticker[3:]}"

        return engine_ticker

    def _oanda_to_engine(self, oanda_symbol: str) -> str:
        """Translate OANDA symbol back to engine ticker."""
        # Remove underscore (EUR_USD → EURUSD)
        return oanda_symbol.replace("_", "")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Make a request to OANDA API."""
        url = urljoin(self._base_url, endpoint)

        try:
            if method == "GET":
                response = self._session.get(
                    url,
                    headers=self._headers,
                    params=params,
                    timeout=REQUEST_TIMEOUT_S,
                )
            elif method == "POST":
                response = self._session.post(
                    url,
                    headers=self._headers,
                    json=data,
                    timeout=REQUEST_TIMEOUT_S,
                )
            elif method == "PUT":
                response = self._session.put(
                    url,
                    headers=self._headers,
                    json=data,
                    timeout=REQUEST_TIMEOUT_S,
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("OANDA API error: %s %s — %s", method, endpoint, e)
            raise ConnectionError(str(e))

    def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("OANDAClient shutting down...")
        self._session.close()
        self._connected = False
