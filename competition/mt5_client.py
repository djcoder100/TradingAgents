# competition/mt5_client.py
"""MetaTrader 5 broker adapter.

Implements AbstractBrokerClient for live MT5 trading with reconnect resilience
and async fill polling.

Connection: Handles login/logout and connection health checks.
Orders: Converts RegulatedOrder to MT5 native orders, tracks fills via polling.
Positions: Syncs open positions from MT5 account.
Account: Tracks equity, margin, leverage, and account metrics.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Dict, List

from competition.api_client import AbstractBrokerClient
from competition.models import (
    AccountState,
    RegulatedOrder,
    Position,
    OrderResult,
    OrderAction,
    ApprovalStatus,
)
from competition.mt5_config import (
    MT5_ACCOUNT_NUMBER,
    MT5_PASSWORD,
    MT5_SERVER,
    MT5_TIMEOUT_S,
    MT5_TERMINAL_PATH,
)
from competition.mt5_symbol_mapper import MT5SymbolMapper
from competition.mt5_fill_poller import MT5FillPoller

logger = logging.getLogger(__name__)


class MT5Client(AbstractBrokerClient):
    """MetaTrader 5 broker client with resilient reconnection and async fills."""

    def __init__(self):
        """Initialize MT5 client and establish connection."""
        try:
            import MetaTrader5 as mt5
        except ImportError:
            raise ImportError(
                "MetaTrader5 package not found. Install it with: pip install MetaTrader5"
            )

        self._mt5 = mt5
        self._connected = False
        self._lock = threading.Lock()

        # Core components
        self._symbol_mapper = MT5SymbolMapper()
        self._symbol_mapper.set_mt5_module(mt5)
        self._fill_poller = MT5FillPoller(mt5)

        # Order tracking: order_id → OrderResult
        self._orders: Dict[str, OrderResult] = {}

        # Connection state
        self._last_health_check = 0

        # Verify credentials before starting
        if not MT5_ACCOUNT_NUMBER or not MT5_PASSWORD or not MT5_SERVER:
            raise ValueError(
                "MT5 credentials incomplete. Set MT5_ACCOUNT_NUMBER, MT5_PASSWORD, MT5_SERVER env vars"
            )

        logger.info(
            "MT5Client initializing — account=%s, server=%s, type=%s",
            MT5_ACCOUNT_NUMBER,
            MT5_SERVER,
            "demo" if not MT5_PASSWORD.startswith("live_") else "live",
        )

        # Initial connection
        if not self.reconnect():
            raise ConnectionError(f"Failed to initialize MT5 connection to {MT5_SERVER}")

        # Start fill poller
        self._fill_poller.start()

    # ======================================================================
    # Connection Management (AbstractBrokerClient pattern)
    # ======================================================================

    def is_connected(self) -> bool:
        """Check if connected to MT5 broker."""
        if not self._connected:
            return False

        # Periodic health check
        now = time.time()
        if now - self._last_health_check > 30:  # Check every 30s
            try:
                account_info = self._mt5.account_info()
                if account_info is None:
                    logger.warning("MT5 health check failed: account_info returned None")
                    self._connected = False
                    return False
                self._last_health_check = now
            except Exception as e:
                logger.warning("MT5 health check failed: %s", e)
                self._connected = False
                return False

        return True

    def reconnect(self) -> bool:
        """Reconnect to MT5 broker."""
        with self._lock:
            try:
                # Initialize MT5 (may be called multiple times)
                if not self._mt5.initialize(
                    path=MT5_TERMINAL_PATH,
                    login=MT5_ACCOUNT_NUMBER,
                    password=MT5_PASSWORD,
                    server=MT5_SERVER,
                    timeout=MT5_TIMEOUT_S * 1000,  # MT5 uses ms
                ):
                    logger.error("MT5.initialize() failed: %s", self._mt5.last_error())
                    self._connected = False
                    return False

                # Verify login
                account_info = self._mt5.account_info()
                if account_info is None:
                    logger.error("MT5 login failed: account_info returned None")
                    self._connected = False
                    return False

                logger.info(
                    "✓ Connected to MT5: %s (equity=%.2f, margin_free=%.2f)",
                    account_info.name,
                    account_info.equity,
                    account_info.margin_free,
                )
                self._connected = True
                self._last_health_check = time.time()

                # Pre-load symbol specs for known instruments
                # TODO: Get this from engine's instrument list
                # self._symbol_mapper.preload_symbols(["EURUSD", "XAUUSD", "BARUSD"])

                return True

            except Exception as e:
                logger.error("MT5 reconnect failed: %s", e)
                self._connected = False
                return False

    # ======================================================================
    # Core Broker API (AbstractBrokerClient contract)
    # ======================================================================

    def get_account_state(self) -> AccountState:
        """Return current account state (equity, margin, positions, leverage)."""
        return self.call_with_retry(self._mt5_get_account_state)

    def _mt5_get_account_state(self) -> AccountState:
        """Fetch account state from MT5."""
        try:
            account_info = self._mt5.account_info()
            if account_info is None:
                raise ConnectionError("account_info returned None")

            return AccountState(
                balance=account_info.balance,
                equity=account_info.equity,
                margin_used=account_info.margin,
                margin_free=account_info.margin_free,
                margin_level=account_info.margin_level or 0,
                leverage=account_info.leverage or 1,
                open_positions_count=len(self._mt5.positions_get()),
                open_orders_count=len(self._mt5.orders_get()),
                currency=account_info.currency or "USD",
            )
        except Exception as e:
            logger.error("Failed to fetch account state: %s", e)
            raise

    def get_positions(self) -> list[Position]:
        """Return all open positions."""
        return self.call_with_retry(self._mt5_get_positions)

    def _mt5_get_positions(self) -> list[Position]:
        """Fetch open positions from MT5."""
        try:
            mt5_positions = self._mt5.positions_get()
            positions = []

            for pos in mt5_positions:
                # Map MT5 symbol back to engine ticker (reverse lookup)
                # For now, assume MT5 symbol == engine ticker
                engine_ticker = pos.symbol

                position = Position(
                    ticker=engine_ticker,
                    direction="BUY" if pos.type == 0 else "SELL",  # 0=BUY, 1=SELL
                    size=pos.volume,
                    entry_price=pos.price_open,
                    current_price=self._get_current_price(pos.symbol),
                    unrealized_pnl=pos.profit,
                    timestamp=pos.time,
                )
                positions.append(position)

            return positions
        except Exception as e:
            logger.error("Failed to fetch positions: %s", e)
            raise

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Return bid/ask midpoint for each ticker."""
        return self.call_with_retry(self._mt5_get_prices, tickers)

    def _mt5_get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Fetch prices from MT5."""
        prices = {}
        try:
            for ticker in tickers:
                mt5_symbol = self._symbol_mapper.engine_to_mt5(ticker)
                symbol_info = self._mt5.symbol_info(mt5_symbol)

                if symbol_info is None:
                    logger.warning("Symbol %s (mapped to %s) not found on broker", ticker, mt5_symbol)
                    prices[ticker] = None
                else:
                    # Midpoint = (bid + ask) / 2
                    mid = (symbol_info.bid + symbol_info.ask) / 2.0
                    prices[ticker] = mid

            return prices
        except Exception as e:
            logger.error("Failed to fetch prices: %s", e)
            raise

    def place_order(self, order: RegulatedOrder) -> OrderResult:
        """Submit a regulated order to MT5."""
        return self.call_with_retry(self._mt5_place_order, order)

    def _mt5_place_order(self, order: RegulatedOrder) -> OrderResult:
        """Execute order placement on MT5."""
        try:
            # Map engine ticker to MT5 symbol
            mt5_symbol = self._symbol_mapper.engine_to_mt5(order.ticker)

            # Get current price
            symbol_info = self._mt5.symbol_info(mt5_symbol)
            if symbol_info is None:
                raise ValueError(f"Symbol {mt5_symbol} not found on broker")

            # Calculate volume from notional
            current_price = (symbol_info.bid + symbol_info.ask) / 2.0
            contract_size = getattr(symbol_info, "trade_contract_size", 1.0)
            volume = order.order_size_notional / (current_price * contract_size)
            volume = max(volume, getattr(symbol_info, "volume_min", 0.01))

            # Build MT5 order request
            action = self._mt5.TRADE_ACTION_DEAL if order.order_type == "MARKET" else self._mt5.TRADE_ACTION_PENDING
            order_type = (
                self._mt5.ORDER_TYPE_BUY if order.action == OrderAction.BUY else self._mt5.ORDER_TYPE_SELL
            ) if order.order_type == "MARKET" else (
                self._mt5.ORDER_TYPE_BUY_LIMIT if order.action == OrderAction.BUY else self._mt5.ORDER_TYPE_SELL_LIMIT
            )

            request = {
                "action": action,
                "symbol": mt5_symbol,
                "volume": volume,
                "type": order_type,
                "price": order.limit_price or current_price,
                "sl": order.stop_loss,
                "tp": order.take_profit,
                "type_time": self._mt5.ORDER_TIME_GTC,  # Good-till-cancelled
                "comment": f"TradingAgents {order.ticker}",
            }

            logger.info(
                "Placing %s order: %s %s %.2f @ %.4f (notional: $%.0f)",
                order.order_type,
                order.action.value,
                mt5_symbol,
                volume,
                request["price"],
                order.order_size_notional,
            )

            result = self._mt5.order_send(request)

            if result.retcode != self._mt5.TRADE_RETCODE_DONE:
                error_msg = f"MT5 order rejected: {result.comment} (retcode={result.retcode})"
                logger.error(error_msg)
                return OrderResult(
                    order_id=None,
                    status=ApprovalStatus.REJECTED,
                    reason=error_msg,
                    filled_price=None,
                    filled_size=0,
                    timestamp=time.time(),
                )

            order_id = str(result.order)
            logger.info("✓ Order placed: %s (order_id=%s)", mt5_symbol, order_id)

            # Determine if it fills immediately or needs polling
            if order.order_type == "MARKET":
                # Market orders fill immediately
                return OrderResult(
                    order_id=order_id,
                    status=ApprovalStatus.FILLED,
                    filled_price=result.price,
                    filled_size=volume,
                    timestamp=time.time(),
                )
            else:
                # Limit orders need polling
                order_result = OrderResult(
                    order_id=order_id,
                    status=ApprovalStatus.PENDING,
                    reason=f"Limit order placed @ {order.limit_price}",
                    timestamp=time.time(),
                )

                # Register for fill polling
                self._fill_poller.register_order(
                    order_id,
                    callback=self._on_order_fill,
                    order_data={"ticker": order.ticker, "action": order.action.value},
                )

                with self._lock:
                    self._orders[order_id] = order_result

                return order_result

        except Exception as e:
            logger.error("Failed to place order on MT5: %s", e)
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        return self.call_with_retry(self._mt5_cancel_order, order_id)

    def _mt5_cancel_order(self, order_id: str) -> bool:
        """Execute order cancellation on MT5."""
        try:
            request = {
                "action": self._mt5.TRADE_ACTION_REMOVE,
                "order": int(order_id),
            }

            result = self._mt5.order_send(request)
            success = result.retcode == self._mt5.TRADE_RETCODE_DONE

            if success:
                logger.info("✓ Order %s cancelled", order_id)
                self._fill_poller.unregister_order(order_id)
            else:
                logger.error("Failed to cancel order %s: %s", order_id, result.comment)

            return success
        except Exception as e:
            logger.error("Error cancelling order %s: %s", order_id, e)
            return False

    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """Get the status of a previously placed order."""
        with self._lock:
            return self._orders.get(order_id)

    # ======================================================================
    # Internal Helpers
    # ======================================================================

    def _get_current_price(self, mt5_symbol: str) -> float:
        """Get current mid price for a symbol."""
        try:
            symbol_info = self._mt5.symbol_info(mt5_symbol)
            if symbol_info:
                return (symbol_info.bid + symbol_info.ask) / 2.0
        except Exception:
            pass
        return None

    def _on_order_fill(self, order_id: str, fill_details: Dict) -> None:
        """Callback invoked when a limit order fills."""
        try:
            with self._lock:
                if order_id in self._orders:
                    self._orders[order_id].status = ApprovalStatus.FILLED
                    self._orders[order_id].filled_price = fill_details.get("price_open")
                    self._orders[order_id].filled_size = fill_details.get("volume_initial")
                    self._orders[order_id].timestamp = fill_details.get("time_fill", time.time())

            logger.info(
                "✓ Order %s filled: %s @ %.4f",
                order_id,
                fill_details.get("ticker", "?"),
                fill_details.get("price_open"),
            )
        except Exception as e:
            logger.error("Error in fill callback for %s: %s", order_id, e)

    def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("MT5Client shutting down...")
        self._fill_poller.stop()
        try:
            self._mt5.shutdown()
        except Exception as e:
            logger.warning("Error during MT5 shutdown: %s", e)
        self._connected = False
