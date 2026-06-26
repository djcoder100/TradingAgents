# competition/alpaca_client.py
"""Alpaca broker adapter (REST API).

Alpaca provides a modern REST API that works perfectly on macOS.
Supports stocks, options, crypto, and forex trading via paper or live accounts.

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
from competition.alpaca_config import (
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    ALPACA_BASE_URL,
    ALPACA_DATA_BASE_URL,
    ALPACA_IS_PAPER,
    ALPACA_SYMBOL_OVERRIDES,
    ALPACA_DEFAULT_SYMBOLS,
    REQUEST_TIMEOUT_S,
)

logger = logging.getLogger(__name__)


class AlpacaClient(AbstractBrokerClient):
    """Alpaca REST API broker client.

    Works on macOS, Linux, Windows. Supports paper and live trading.
    """

    def __init__(self):
        """Initialize Alpaca client."""
        if not ALPACA_API_KEY or not ALPACA_API_SECRET:
            raise ValueError(
                "Alpaca credentials missing. Set ALPACA_API_KEY and ALPACA_API_SECRET env vars. "
                "Get them from https://app.alpaca.markets/paper/dashboard/overview"
            )

        self._api_key = ALPACA_API_KEY
        self._api_secret = ALPACA_API_SECRET
        self._base_url = ALPACA_BASE_URL
        self._data_url = ALPACA_DATA_BASE_URL
        self._session = requests.Session()
        self._headers = {
            "APCA-API-KEY-ID": self._api_key,
        }
        self._connected = False
        self._last_health_check = 0
        self._orders: Dict[str, OrderResult] = {}

        logger.info(
            "AlpacaClient initializing — mode=%s, endpoint=%s",
            "PAPER" if ALPACA_IS_PAPER else "LIVE",
            self._base_url,
        )

        # Verify connection
        if not self.reconnect():
            raise ConnectionError("Failed to connect to Alpaca")

        logger.info("✓ Connected to Alpaca")

    # ======================================================================
    # Connection Management
    # ======================================================================

    def is_connected(self) -> bool:
        """Check if connected to Alpaca."""
        if not self._connected:
            return False

        # Periodic health check every 30s
        now = time.time()
        if now - self._last_health_check > 30:
            try:
                account = self._request("GET", "/v2/account")
                self._last_health_check = now
                if account:
                    return True
            except Exception as e:
                logger.warning("Alpaca health check failed: %s", e)
                self._connected = False
                return False

        return True

    def reconnect(self) -> bool:
        """Reconnect to Alpaca."""
        try:
            # Test connection by fetching account info
            account = self._request("GET", "/v2/account")
            if account is None:
                logger.error("Failed to fetch account info")
                self._connected = False
                return False

            logger.info(
                "✓ Connected to Alpaca: %s (equity=$%.2f, buying_power=$%.2f)",
                account.get("account_number", "?"),
                account.get("equity", 0),
                account.get("buying_power", 0),
            )
            self._connected = True
            self._last_health_check = time.time()
            return True

        except Exception as e:
            logger.error("Alpaca reconnect failed: %s", e)
            self._connected = False
            return False

    # ======================================================================
    # Core Broker API
    # ======================================================================

    def get_account_state(self) -> AccountState:
        """Return current account state."""
        return self.call_with_retry(self._alpaca_get_account_state)

    def _alpaca_get_account_state(self) -> AccountState:
        """Fetch account state from Alpaca."""
        try:
            account = self._request("GET", "/v2/account")
            if account is None:
                raise ConnectionError("account info returned None")

            return AccountState(
                balance=float(account.get("cash", 0)),
                equity=float(account.get("equity", 0)),
                margin_used=float(account.get("equity", 0)) - float(account.get("buying_power", 0)),
                margin_free=float(account.get("buying_power", 0)),
                margin_level=100.0,  # Alpaca doesn't expose margin level directly
                leverage=1.0,  # Alpaca doesn't allow leverage for stocks
                open_positions_count=len(self._request("GET", "/v2/positions") or []),
                open_orders_count=len(self._request("GET", "/v2/orders?status=open") or []),
                currency="USD",
            )
        except Exception as e:
            logger.error("Failed to fetch account state: %s", e)
            raise

    def get_positions(self) -> list[Position]:
        """Return all open positions."""
        return self.call_with_retry(self._alpaca_get_positions)

    def _alpaca_get_positions(self) -> list[Position]:
        """Fetch open positions from Alpaca."""
        try:
            positions_data = self._request("GET", "/v2/positions")
            if positions_data is None:
                return []

            positions = []
            for pos in positions_data:
                position = Position(
                    ticker=pos["symbol"],
                    direction="BUY" if float(pos["qty"]) > 0 else "SELL",
                    size=abs(float(pos["qty"])),
                    entry_price=float(pos.get("avg_entry_price", 0)),
                    current_price=float(pos.get("current_price", 0)),
                    unrealized_pnl=float(pos.get("unrealized_pl", 0)),
                    timestamp=int(time.time()),
                )
                positions.append(position)

            return positions
        except Exception as e:
            logger.error("Failed to fetch positions: %s", e)
            raise

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Return bid/ask midpoint for each ticker."""
        return self.call_with_retry(self._alpaca_get_prices, tickers)

    def _alpaca_get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Fetch prices from Alpaca."""
        prices = {}
        try:
            for ticker in tickers:
                alpaca_symbol = self._engine_to_alpaca(ticker)

                # Use stock quote endpoint
                quote = self._request("GET", f"/v2/stocks/{alpaca_symbol}/quotes/latest")
                if quote and "quote" in quote:
                    quote_data = quote["quote"]
                    bid = float(quote_data.get("bp", 0))
                    ask = float(quote_data.get("ap", 0))
                    if bid > 0 and ask > 0:
                        mid = (bid + ask) / 2.0
                        prices[ticker] = mid
                    else:
                        logger.warning("Invalid quote for %s: bid=%.2f ask=%.2f", ticker, bid, ask)
                        prices[ticker] = None
                else:
                    logger.warning("No quote data for %s", ticker)
                    prices[ticker] = None

            return prices
        except Exception as e:
            logger.error("Failed to fetch prices: %s", e)
            raise

    def place_order(self, order: RegulatedOrder) -> OrderResult:
        """Submit a regulated order to Alpaca."""
        return self.call_with_retry(self._alpaca_place_order, order)

    def _alpaca_place_order(self, order: RegulatedOrder) -> OrderResult:
        """Execute order placement on Alpaca."""
        try:
            alpaca_symbol = self._engine_to_alpaca(order.ticker)

            # Alpaca order request
            request_data = {
                "symbol": alpaca_symbol,
                "qty": order.order_size_notional / 100,  # Convert notional to shares (rough estimate)
                "side": "buy" if order.action == OrderAction.BUY else "sell",
                "type": "market" if order.order_type == "MARKET" else "limit",
                "time_in_force": "day",
            }

            # Add limit price if specified
            if order.order_type == "LIMIT" and order.limit_price:
                request_data["limit_price"] = order.limit_price

            logger.info(
                "Placing %s order: %s %s (notional: $%.0f)",
                order.order_type,
                order.action.value.upper(),
                alpaca_symbol,
                order.order_size_notional,
            )

            result = self._request("POST", "/v2/orders", data=request_data)

            if result is None:
                error_msg = "Alpaca order placement returned None"
                logger.error(error_msg)
                return OrderResult(
                    order_id=None,
                    status=ApprovalStatus.REJECTED,
                    reason=error_msg,
                    filled_price=None,
                    filled_size=0,
                    timestamp=time.time(),
                )

            order_id = result["id"]
            status_str = result.get("status", "pending_new")

            # Check if order was filled immediately (market orders)
            if status_str in ("filled", "partially_filled"):
                filled_qty = float(result.get("filled_qty", 0))
                filled_price = float(result.get("filled_avg_price", 0))
                return OrderResult(
                    order_id=order_id,
                    status=ApprovalStatus.FILLED,
                    filled_price=filled_price,
                    filled_size=filled_qty,
                    timestamp=time.time(),
                )
            else:
                # Order is pending
                order_result = OrderResult(
                    order_id=order_id,
                    status=ApprovalStatus.PENDING,
                    reason=f"Order pending: {status_str}",
                    timestamp=time.time(),
                )

                with self._lock if hasattr(self, '_lock') else __import__('threading').Lock():
                    self._orders[order_id] = order_result

                logger.info("✓ Order placed: %s (order_id=%s, status=%s)", alpaca_symbol, order_id, status_str)
                return order_result

        except Exception as e:
            logger.error("Failed to place order on Alpaca: %s", e)
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        return self.call_with_retry(self._alpaca_cancel_order, order_id)

    def _alpaca_cancel_order(self, order_id: str) -> bool:
        """Execute order cancellation on Alpaca."""
        try:
            result = self._request("DELETE", f"/v2/orders/{order_id}")
            if result:
                logger.info("✓ Order %s cancelled", order_id)
                return True
            else:
                logger.error("Failed to cancel order %s", order_id)
                return False
        except Exception as e:
            logger.error("Error cancelling order %s: %s", order_id, e)
            return False

    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """Get the status of a previously placed order."""
        try:
            result = self._request("GET", f"/v2/orders/{order_id}")
            if result is None:
                return None

            status_str = result.get("status", "")
            status_map = {
                "filled": ApprovalStatus.FILLED,
                "partially_filled": ApprovalStatus.PENDING,
                "pending_new": ApprovalStatus.PENDING,
                "pending_cancel": ApprovalStatus.PENDING,
                "canceled": ApprovalStatus.REJECTED,
                "expired": ApprovalStatus.REJECTED,
                "rejected": ApprovalStatus.REJECTED,
            }

            return OrderResult(
                order_id=order_id,
                status=status_map.get(status_str, ApprovalStatus.PENDING),
                filled_price=float(result.get("filled_avg_price", 0)) or None,
                filled_size=float(result.get("filled_qty", 0)),
                timestamp=time.time(),
            )
        except Exception as e:
            logger.error("Failed to get order status for %s: %s", order_id, e)
            return None

    # ======================================================================
    # Internal Helpers
    # ======================================================================

    def _engine_to_alpaca(self, engine_ticker: str) -> str:
        """Translate engine ticker to Alpaca symbol."""
        # 1. Check explicit overrides
        if engine_ticker in ALPACA_SYMBOL_OVERRIDES:
            return ALPACA_SYMBOL_OVERRIDES[engine_ticker]

        # 2. Check default mapping
        if engine_ticker in ALPACA_DEFAULT_SYMBOLS:
            return ALPACA_DEFAULT_SYMBOLS[engine_ticker]

        # 3. Fallback to engine ticker as-is
        return engine_ticker

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Make a request to Alpaca API."""
        url = urljoin(self._base_url, endpoint)

        try:
            if method == "GET":
                response = self._session.get(
                    url,
                    headers=self._headers,
                    timeout=REQUEST_TIMEOUT_S,
                )
            elif method == "POST":
                response = self._session.post(
                    url,
                    headers=self._headers,
                    json=data,
                    timeout=REQUEST_TIMEOUT_S,
                )
            elif method == "DELETE":
                response = self._session.delete(
                    url,
                    headers=self._headers,
                    timeout=REQUEST_TIMEOUT_S,
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("Alpaca API error: %s %s — %s", method, endpoint, e)
            raise ConnectionError(str(e))

    def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("AlpacaClient shutting down...")
        self._session.close()
        self._connected = False
