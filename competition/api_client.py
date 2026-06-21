# competition/api_client.py
"""Broker API abstraction layer.

Provides an abstract interface (ABC) so the engine is decoupled from
any specific broker implementation.  A ``MockBrokerClient`` ships for
local development/testing before the competition system goes live.
"""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from competition.models import (
    AccountState,
    RegulatedOrder,
    Position,
    OrderResult,
    OrderAction,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class AbstractBrokerClient(ABC):
    """Contract that every broker adapter must satisfy."""

    @abstractmethod
    def get_account_state(self) -> AccountState:
        """Return the latest account snapshot."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return all currently open positions."""

    @abstractmethod
    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        """Return latest bid/ask midpoint for each ticker."""

    @abstractmethod
    def place_order(self, order: RegulatedOrder) -> OrderResult:
        """Submit an order. Called ONLY after firewall approval."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Attempt to cancel a pending order. Returns True if successful."""

    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """Return the current status of a previously placed order."""

    # ------------------------------------------------------------------
    # Reconnect pattern (MT5 / live broker)
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        """Override to return False when the connection is known to be down."""
        return True

    def reconnect(self) -> bool:
        """Override with broker-specific reconnect logic.

        Called automatically by call_with_retry() when is_connected() is False
        or when a call raises a connection-related exception.
        Returns True if the reconnect succeeded.
        """
        return True

    def call_with_retry(self, fn, *args, max_attempts: int = 3, backoff_s: float = 2.0, **kwargs):
        """Call *fn* with exponential backoff on connection failure.

        Usage (in concrete subclasses):
            return self.call_with_retry(self._mt5_get_account)

        On each failure the client calls reconnect(); if reconnect() fails
        after *max_attempts* retries the last exception is re-raised.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                if not self.is_connected():
                    logger.warning("Broker not connected — attempting reconnect (try %d/%d)", attempt, max_attempts)
                    if not self.reconnect():
                        raise ConnectionError("Broker reconnect returned False")
                return fn(*args, **kwargs)
            except (ConnectionError, OSError, TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "Broker call failed (try %d/%d): %s. Reconnecting in %.1fs...",
                    attempt, max_attempts, exc, backoff_s,
                )
                time.sleep(backoff_s)
                backoff_s = min(backoff_s * 2, 30.0)  # cap at 30s
                self.reconnect()
        raise last_exc or ConnectionError("Broker call failed after all retries")


# ---------------------------------------------------------------------------
# Mock implementation — simulates a broker for local testing
# ---------------------------------------------------------------------------

class MockBrokerClient(AbstractBrokerClient):
    """In-memory broker simulator.

    Starts with $1M equity. Prices are synthetic and drift randomly.
    Fills are simulated at the current mock price. Thread-safe for
    the single-threaded engine loop.
    """

    # Typical half-spread per instrument class (in price units)
    # Used to simulate bid/ask spread: BUY fills at mid+half_spread, SELL at mid-half_spread
    _HALF_SPREAD: dict[str, float] = {
        "EURUSD": 0.00005, "GBPUSD": 0.00007, "USDJPY": 0.007,
        "USDCHF": 0.00008, "USDCAD": 0.00010, "AUDUSD": 0.00008,
        "NZDUSD": 0.00010,
    }
    _HALF_SPREAD_DEFAULT_FX    = 0.00015   # crosses / less liquid Forex
    _HALF_SPREAD_DEFAULT_METAL = 0.15      # Gold ~$0.15 half-spread
    _HALF_SPREAD_DEFAULT_CRYPTO = 2.0      # crypto ~$2 half-spread

    def __init__(
        self,
        initial_equity: float = 1_000_000.0,
        instruments: Optional[list[str]] = None,
        leverage_multiplier: float = 30.0,
    ):
        self._lock = threading.Lock()
        self._equity = initial_equity
        self._leverage_multiplier = leverage_multiplier

        # Synthetic prices — seed with plausible starting values
        self._prices: dict[str, float] = {}
        self._base_prices = {
            # Forex (quote to 5 d.p.)
            "EURUSD": 1.0850, "GBPUSD": 1.2720, "USDJPY": 154.80,
            "USDCHF": 0.9130, "USDCAD": 1.3670, "AUDUSD": 0.6620,
            "NZDUSD": 0.6120,
            "EURGBP": 0.8530, "EURJPY": 168.00, "GBPJPY": 197.00,
            "EURCHF": 0.9900, "AUDJPY": 102.50, "NZDJPY": 94.70,
            "CADJPY": 113.20, "GBPCHF": 1.1610, "EURAUD": 1.6390,
            "EURCAD": 1.4830, "GBPAUD": 1.9210, "GBPCAD": 1.7390,
            "AUDCAD": 0.9050, "AUDCHF": 0.6040, "AUDNZD": 1.0810,
            "EURNZD": 1.7730, "GBPNZD": 2.0780, "NZDCAD": 0.8370,
            "NZDCHF": 0.5580,
            # Metals
            "XAUUSD": 2350.0, "XAGUSD": 28.50,
            # Crypto
            "BTCUSD": 67500.0, "ETHUSD": 3480.0, "SOLUSD": 165.0,
            "XRPUSD": 0.62, "DOGEUSD": 0.125,
            "BARUSD": 0.085,  # HBAR/Hedera — confirm contract spec at MT5 login
        }
        # Initialize all requested instruments
        for t in (instruments or []):
            if t not in self._base_prices:
                self._base_prices[t] = 100.0  # generic fallback
        self._prices = dict(self._base_prices)

        self._positions: dict[str, Position] = {}  # keyed by position id
        self._orders: dict[str, OrderResult] = {}
        # Pending LIMIT orders: order_id → (order, limit_price)
        self._pending_limits: dict[str, tuple[RegulatedOrder, float]] = {}
        self._used_margin = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_account_state(self) -> AccountState:
        with self._lock:
            gross = sum(
                p.size_notional for p in self._positions.values()
            )
            return AccountState(
                equity=self._equity,
                used_margin=self._used_margin,
                gross_notional_exposure=gross,
                open_positions_count=len(self._positions),
                buying_power=self._equity * self._leverage_multiplier - self._used_margin,
            )

    def get_positions(self) -> list[Position]:
        with self._lock:
            # Update unrealized PnL from latest prices
            result = []
            for pos in self._positions.values():
                px = self._prices.get(pos.ticker, pos.avg_entry_price)
                if pos.direction == OrderAction.BUY:
                    pnl = (px - pos.avg_entry_price) / pos.avg_entry_price * pos.size_notional
                else:
                    pnl = (pos.avg_entry_price - px) / pos.avg_entry_price * pos.size_notional
                pos.current_px = px
                pos.unrealized_pnl = pnl
                result.append(pos)
            return result

    def get_prices(self, tickers: list[str]) -> dict[str, float]:
        with self._lock:
            return {t: self._prices.get(t, 100.0) for t in tickers}

    def _half_spread(self, ticker: str) -> float:
        if ticker in self._HALF_SPREAD:
            return self._HALF_SPREAD[ticker]
        if ticker in ("XAUUSD", "XAGUSD"):
            return self._HALF_SPREAD_DEFAULT_METAL
        if any(ticker.startswith(c) for c in ("BTC", "ETH", "SOL", "XRP", "DOGE", "BAR")):
            return self._HALF_SPREAD_DEFAULT_CRYPTO
        return self._HALF_SPREAD_DEFAULT_FX

    def place_order(self, order: RegulatedOrder) -> OrderResult:
        oid = f"mock-{uuid.uuid4().hex[:8]}"
        with self._lock:
            mid = self._prices.get(order.ticker, 100.0)
            half_spread = self._half_spread(order.ticker)

            if order.order_type == "LIMIT" and order.limit_price is not None:
                # Post resting limit — park it in the pending queue
                result = OrderResult(
                    order_id=oid,
                    status="PENDING",
                    ticker=order.ticker,
                    action=order.action,
                    filled_size=0.0,
                    filled_price=None,
                )
                self._orders[oid] = result
                self._pending_limits[oid] = (order, order.limit_price)
                logger.info(
                    "Mock limit posted: %s %s %s @ %.5f (mid=%.5f) size=$%.0f",
                    oid, order.action.value, order.ticker,
                    order.limit_price, mid, order.order_size_notional,
                )
                return result

            # MARKET order — fill immediately with simulated spread
            if order.action == OrderAction.BUY:
                fill_px = mid + half_spread   # buyer pays ask
            else:
                fill_px = mid - half_spread   # seller receives bid

            result = OrderResult(
                order_id=oid,
                status="FILLED",
                ticker=order.ticker,
                action=order.action,
                filled_size=order.order_size_notional,
                filled_price=fill_px,
            )
            self._orders[oid] = result
            self._fill_order(oid, order, fill_px)

        logger.info(
            "Mock fill: %s %s %s @ %.5f (spread=%.5f) size=$%.0f",
            oid, order.action.value, order.ticker,
            fill_px, half_spread * 2, order.order_size_notional,
        )
        return result

    def _fill_order(self, oid: str, order: RegulatedOrder, fill_px: float) -> None:
        """Apply a fill — update positions and equity. Must be called under lock."""
        if order.action == OrderAction.BUY:
            self._close_matching(order.ticker, OrderAction.SELL, fill_px)
            pos = Position(
                ticker=order.ticker,
                size_notional=order.order_size_notional,
                direction=OrderAction.BUY,
                avg_entry_price=fill_px,
                current_px=fill_px,
                unrealized_pnl=0.0,
            )
            self._positions[oid] = pos
            self._used_margin += order.order_size_notional / self._leverage_multiplier
        elif order.action == OrderAction.SELL:
            self._close_matching(order.ticker, OrderAction.BUY, fill_px)
            pos = Position(
                ticker=order.ticker,
                size_notional=order.order_size_notional,
                direction=OrderAction.SELL,
                avg_entry_price=fill_px,
                current_px=fill_px,
                unrealized_pnl=0.0,
            )
            self._positions[oid] = pos
            self._used_margin += order.order_size_notional / self._leverage_multiplier

    def cancel_order(self, order_id: str) -> bool:
        with self._lock:
            if order_id in self._pending_limits:
                order, _ = self._pending_limits.pop(order_id)
                self._orders[order_id] = OrderResult(
                    order_id=order_id,
                    status="CANCELLED",
                    ticker=order.ticker,
                    action=order.action,
                    filled_size=0.0,
                )
                logger.debug("Mock limit cancelled: %s", order_id)
                return True
            if order_id in self._orders:
                self._orders[order_id] = OrderResult(
                    order_id=order_id,
                    status="CANCELLED",
                    ticker=self._orders[order_id].ticker,
                    action=self._orders[order_id].action,
                    filled_size=0.0,
                )
                return True
            return False

    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        with self._lock:
            return self._orders.get(order_id)

    # ------------------------------------------------------------------
    # Simulation helpers (not part of ABC)
    # ------------------------------------------------------------------

    def _close_matching(self, ticker: str, direction: OrderAction, px: float) -> None:
        """Close the first matching position (same ticker + direction)."""
        for pid, pos in list(self._positions.items()):
            if pos.ticker == ticker and pos.direction == direction:
                if direction == OrderAction.BUY:
                    realized = (px - pos.avg_entry_price) / pos.avg_entry_price * pos.size_notional
                else:
                    realized = (pos.avg_entry_price - px) / pos.avg_entry_price * pos.size_notional
                self._equity += realized
                self._used_margin -= pos.size_notional / self._leverage_multiplier
                del self._positions[pid]
                logger.debug(
                    "Mock close: %s %s @ %.5f PnL=$%.2f",
                    ticker, direction.value, px, realized,
                )
                break

    def tick_prices(self) -> None:
        """Apply random micro-movements to all synthetic prices, then check limit fills.

        Volatility is instrument-appropriate: wider for crypto, tighter for Forex.
        After price update, any resting limit order whose price is now touched is filled.
        """
        filled_ids = []
        with self._lock:
            for ticker, base in self._base_prices.items():
                # Scale noise to the instrument type
                if ticker.endswith("USD") and ticker[:3] in ("BTC", "ETH", "SOL", "XRP", "DOGE", "BAR"):
                    sigma = 0.003   # 0.3% for crypto
                elif ticker in ("XAUUSD", "XAGUSD"):
                    sigma = 0.001   # 0.1% for metals
                elif "JPY" in ticker:
                    sigma = 0.0003  # 0.03% for JPY pairs
                else:
                    sigma = 0.0005  # 0.05% for other forex

                drift = random.gauss(0, sigma)
                self._prices[ticker] = base * (1 + drift)
                self._base_prices[ticker] = self._prices[ticker]  # random walk

            # Check resting limit orders for fills
            for oid, (order, limit_px) in list(self._pending_limits.items()):
                mid = self._prices.get(order.ticker, 100.0)
                hit = (
                    (order.action == OrderAction.BUY  and mid <= limit_px) or
                    (order.action == OrderAction.SELL and mid >= limit_px)
                )
                if hit:
                    self._orders[oid] = OrderResult(
                        order_id=oid,
                        status="FILLED",
                        ticker=order.ticker,
                        action=order.action,
                        filled_size=order.order_size_notional,
                        filled_price=limit_px,  # fill at the posted limit (maker price)
                    )
                    self._fill_order(oid, order, limit_px)
                    del self._pending_limits[oid]
                    filled_ids.append((oid, order, limit_px))

        for oid, order, px in filled_ids:
            logger.info(
                "Mock limit filled: %s %s %s @ %.5f size=$%.0f",
                oid, order.action.value, order.ticker, px, order.order_size_notional,
            )
