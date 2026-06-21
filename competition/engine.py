# competition/engine.py
"""Main competition loop — wires all components together.

The engine runs a tight polling loop:
  1. Fetch account state, positions, prices from broker
  2. Check exit conditions for all open positions
  3. Check entry conditions for active signals
  4. Every 15 min: refresh TradingAgents signals, record equity snapshot, audit compliance
  5. Log scoring metrics for operator visibility

All orders pass through the ExecutionEngine risk firewall before dispatch.
"""

from __future__ import annotations

import logging
import signal as os_signal
import sys
import threading
import time
from datetime import datetime
from typing import Optional

from competition.config import (
    DEFAULT_INSTRUMENTS,
    MAX_CONCURRENT_POSITIONS,
    SIGNAL_STALE_S,
    TRADINGAGENTS_MAX_INSTRUMENTS,
)
from competition.models import (
    TradeSignal,
    TradeRecord,
    RegulatedOrder,
    OrderResult,
    OrderAction,
    ApprovalStatus,
    AccountState,
)
from competition.risk_firewall import ExecutionEngine
from competition.api_client import AbstractBrokerClient
from competition.signal_adapter import SignalAdapter
from competition.indicator_signals import IndicatorSignals
from competition.state_tracker import StateTracker
from competition.scheduler import Scheduler

logger = logging.getLogger(__name__)


class CompetitionEngine:
    """Orchestrates the competition trading bot."""

    def __init__(
        self,
        broker: AbstractBrokerClient,
        instruments: Optional[list[str]] = None,
        signal_adapter: Optional[SignalAdapter] = None,
        firewall: Optional[ExecutionEngine] = None,
        dry_run: bool = False,
        no_llm: bool = False,
        state_bus=None,
    ):
        self.broker = broker
        self.instruments = instruments or DEFAULT_INSTRUMENTS
        self.dry_run = dry_run
        self.no_llm = no_llm
        self.state_bus = state_bus

        self.firewall = firewall or ExecutionEngine()
        self.signal_adapter = signal_adapter or SignalAdapter()
        self.indicators = IndicatorSignals()
        self.tracker = StateTracker(self.firewall)
        self.scheduler = Scheduler()

        # Active signals keyed by ticker
        self.active_signals: dict[str, TradeSignal] = {}
        # Pending limit orders: order_id → (RegulatedOrder, ticker, signal)
        # Tracked so we can cancel them when the signal expires or changes.
        self._pending_limits: dict[str, tuple[RegulatedOrder, str]] = {}
        # Round-trip trade counter (open + close = 1 round-trip).
        # Best Sharpe category requires ≥30 completed round-trips.
        self.round_trip_count = 0
        self._open_orders: dict[str, str] = {}  # ticker → order_id (open leg tracking)
        self._running = False
        self._refresh_running = False  # guards background TA refresh thread

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Run the competition loop until stopped or competition ends."""
        self._running = True
        logger.info(
            "Competition engine starting — %d instruments, dry_run=%s, no_llm=%s",
            len(self.instruments),
            self.dry_run,
            self.no_llm,
        )
        logger.info("Competition window: now → %s", datetime.fromtimestamp(
            self.scheduler._competition_end
        ).isoformat())

        # Initial signal refresh to populate directional views (non-blocking)
        if not self.no_llm:
            self._refresh_running = True
            threading.Thread(target=self._refresh_signals, daemon=True).start()
            logger.info("Background TA signal refresh started...")
        else:
            logger.info("--no-llm mode: skipping TradingAgents, using indicator-only signals")

        try:
            while self._running and self.scheduler.is_competition_active():
                self._tick()
                # Sleep in short increments so Ctrl+C / stop() takes
                # effect within 100ms instead of blocking for the full
                # polling interval.
                for _ in range(int(self.scheduler.polling_interval_s * 10)):
                    if not self._running:
                        break
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received — shutting down")
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Graceful stop (can be called from signal handler)."""
        self._running = False

    # ------------------------------------------------------------------
    # Single tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """One iteration of the main loop."""
        try:
            # 1. Simulate market movement, then fetch current state
            if hasattr(self.broker, "tick_prices"):
                self.broker.tick_prices()
            account = self.broker.get_account_state()
            positions = self.broker.get_positions()
            all_tickers = list(
                set(self.instruments)
                | set(self.tracker.get_active_tickers())
                | set(self.active_signals.keys())
            )
            prices = self.broker.get_prices(all_tickers)

            # Update tracker
            self.tracker.update(account, positions, prices)

            # 2. Check exit conditions
            self._check_exits(account, positions, prices)

            # 3. Check entry conditions for active signals
            self._check_entries(account, prices)

            # 4. Periodic signal refresh (non-blocking — runs in background thread)
            if self.scheduler.should_refresh_signals() and not self._refresh_running:
                self._refresh_running = True
                threading.Thread(target=self._refresh_signals, daemon=True).start()

            # 5. 15-min boundary tasks
            if self.scheduler.is_15min_boundary():
                self._on_15min_boundary(account)

            # 6. Publish state for web dashboard
            if self.state_bus:
                self._publish_state(account)

        except Exception as exc:
            logger.error("Engine tick error: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Exit & entry checking
    # ------------------------------------------------------------------

    def _check_exits(
        self,
        account: AccountState,
        positions: list,
        prices: dict[str, float],
    ) -> None:
        """Check exit conditions for every open position."""
        for pos in positions:
            px = prices.get(pos.ticker, pos.avg_entry_price)
            signal = self.active_signals.get(pos.ticker)
            exit_order = self.indicators.check_exit_conditions(pos, px, signal)
            if exit_order is None:
                continue

            # Exit orders are always MARKET so we close immediately
            exit_order.order_type = "MARKET"
            exit_order.limit_price = None

            approved = self.firewall.verify_and_route(exit_order, account)
            if approved.status == ApprovalStatus.APPROVED:
                self._dispatch(exit_order, is_close=True)
                if signal and signal.is_expired():
                    self.active_signals.pop(pos.ticker, None)
            elif approved.status == ApprovalStatus.MUTATED:
                exit_order.order_size_notional = approved.safe_size or exit_order.order_size_notional
                self._dispatch(exit_order, is_close=True)

    def _check_entries(
        self,
        account: AccountState,
        prices: dict[str, float],
    ) -> None:
        """Check entry conditions for active (non-expired) signals."""
        if self.tracker.position_count() >= MAX_CONCURRENT_POSITIONS:
            return

        # Sharpe-aware position sizing: if running Sharpe < 1.0, cut sizes in half
        # to reduce equity volatility (the Std denominator) — exactly the feedback loop
        # described in the MoMQ rules strategy guide.
        metrics = self.tracker.calculate_scoring_metrics()
        sharpe_scalar = 1.0
        if metrics.sharpe_ratio is not None and metrics.sharpe_ratio < 1.0:
            sharpe_scalar = 0.5
            logger.debug(
                "Sharpe %.2f < 1.0 — applying 0.5x position size scalar to protect Std",
                metrics.sharpe_ratio,
            )

        for ticker, signal in list(self.active_signals.items()):
            if signal.is_expired():
                continue
            if self.tracker.has_position_for(ticker):
                continue  # already in position

            entry_order = self.indicators.get_fast_signal(ticker, signal)
            if entry_order is None:
                continue

            # Apply Sharpe scalar before firewall check
            entry_order.order_size_notional = round(
                entry_order.order_size_notional * sharpe_scalar, 2
            )

            # Cancel any existing pending limit for this ticker before placing a new one
            self._cancel_pending_for_ticker(ticker)

            approved = self.firewall.verify_and_route(entry_order, account)
            if approved.status == ApprovalStatus.APPROVED:
                result = self._dispatch(entry_order)
                if result and entry_order.order_type == "LIMIT":
                    self._pending_limits[result.order_id] = (entry_order, ticker)
                    self._open_orders[ticker] = result.order_id
            elif approved.status == ApprovalStatus.MUTATED:
                entry_order.order_size_notional = approved.safe_size or entry_order.order_size_notional
                if entry_order.order_size_notional > 0:
                    result = self._dispatch(entry_order)
                    if result and entry_order.order_type == "LIMIT":
                        self._pending_limits[result.order_id] = (entry_order, ticker)
                        self._open_orders[ticker] = result.order_id

    # ------------------------------------------------------------------
    # Signal refresh (TradingAgents)
    # ------------------------------------------------------------------

    def _refresh_signals(self) -> None:
        """Run TradingAgents on the top N instruments to refresh directional views.

        In --no-llm mode, generates simple indicator-only placeholder signals
        so the entry/exit gating still has directional context to work with.

        Called from a background daemon thread so the main loop stays responsive
        to Ctrl+C during the 2-3 minute LLM pipeline.
        """
        try:
            if self.no_llm:
                self._generate_indicator_signals()
                return

            candidates = SignalAdapter.select_instruments_to_analyze(
                self.instruments,
                self.active_signals,
                max_count=TRADINGAGENTS_MAX_INSTRUMENTS,
            )
            if not candidates:
                logger.debug("No instruments need signal refresh")
                return

            trade_date = datetime.now().strftime("%Y-%m-%d")
            logger.info("Refreshing TA signals for %d instruments: %s", len(candidates), candidates)

            for ticker in candidates:
                if not self._running:
                    break
                try:
                    decision = self.signal_adapter.run_analysis_for_instrument(
                        ticker, trade_date, state_bus=self.state_bus
                    )
                    if decision is None:
                        continue

                    account = self.broker.get_account_state()
                    signal = self.signal_adapter.portfolio_decision_to_signal(
                        decision, account, ticker
                    )
                    if signal is not None:
                        signal.analysis_id = decision.get("analysis_id")
                        self.active_signals[ticker] = signal
                        # Store analysis for web dashboard
                        if self.state_bus:
                            analysis = decision.get("summary", "") + "\n\n" + decision.get("thesis", "")
                            self.state_bus.set_analysis(ticker, analysis)
                        logger.info(
                            "New signal: %s %s $%.0f (confidence=%.2f, expires in %ds)",
                            signal.action.value,
                            ticker,
                            signal.order_size_notional,
                            signal.confidence,
                            int(signal.expires_at - time.time()),
                        )
                except Exception as exc:
                    logger.error("Signal refresh failed for %s: %s", ticker, exc)

            # Prune expired signals and cancel any resting limit orders for them
            for ticker in list(self.active_signals.keys()):
                if self.active_signals[ticker].is_expired():
                    logger.debug("Pruning expired signal for %s", ticker)
                    self._cancel_pending_for_ticker(ticker)
                    del self.active_signals[ticker]
        finally:
            self._refresh_running = False

    # ------------------------------------------------------------------
    # Indicator-only signal generation (--no-llm mode)
    # ------------------------------------------------------------------

    def _generate_indicator_signals(self) -> None:
        """Generate simple trend-following signals from recent price action.

        Used when --no-llm is set. Picks the top N instruments by recent
        volatility and assigns a direction based on short-term momentum
        (5-period vs 20-period SMA crossover).
        """
        import time as _time
        from competition.config import DEFAULT_POSITION_PCT

        account = self.broker.get_account_state()
        candidates = SignalAdapter.select_instruments_to_analyze(
            self.instruments,
            self.active_signals,
            max_count=TRADINGAGENTS_MAX_INSTRUMENTS,
        )
        if not candidates:
            return

        for ticker in candidates:
            try:
                from competition.indicator_signals import _fetch_recent_data
                df = _fetch_recent_data(ticker, period="5d", interval="1h")
                if df is None or len(df) < 20:
                    continue

                sma5 = df["Close"].rolling(5).mean().iloc[-1]
                sma20 = df["Close"].rolling(20).mean().iloc[-1]
                latest = df["Close"].iloc[-1]

                # Simple momentum: SMA5 > SMA20 → bullish, else bearish
                if sma5 > sma20:
                    action = OrderAction.BUY
                    confidence = 0.45  # lower than LLM signals
                else:
                    action = OrderAction.SELL
                    confidence = 0.45

                notional = account.equity * DEFAULT_POSITION_PCT
                signal = TradeSignal(
                    action=action,
                    ticker=ticker,
                    order_size_notional=round(notional, 2),
                    confidence=confidence,
                    created_at=_time.time(),
                    expires_at=_time.time() + SIGNAL_STALE_S,
                )
                self.active_signals[ticker] = signal
                logger.info(
                    "Indicator signal: %s %s $%.0f (sma5=%.4f sma20=%.4f)",
                    action.value, ticker, notional, sma5, sma20,
                )
            except Exception as exc:
                logger.debug("Indicator signal failed for %s: %s", ticker, exc)

        # Prune expired signals and cancel any resting limit orders for them
        for ticker in list(self.active_signals.keys()):
            if self.active_signals[ticker].is_expired():
                self._cancel_pending_for_ticker(ticker)
                del self.active_signals[ticker]

    # ------------------------------------------------------------------
    # 15-minute boundary
    # ------------------------------------------------------------------

    def _on_15min_boundary(self, account: AccountState) -> None:
        """Tasks to run on each 15-minute mark."""
        self.tracker.maybe_record_snapshot(account)
        self.tracker.check_compliance(account)

        metrics = self.tracker.calculate_scoring_metrics()
        logger.info(
            "SCORING | Return: %+.2f%% | MaxDD: %.2f%% | Sharpe: %s | "
            "Obs: %d/%d | Leverage: %.1fx | Margin: %.1f%% | "
            "RoundTrips: %d/30 | Uptime: %s",
            metrics.total_return_pct,
            metrics.max_drawdown_pct,
            f"{metrics.sharpe_ratio:.2f}" if metrics.sharpe_ratio is not None else "N/A",
            metrics.intervals_recorded,
            metrics.intervals_needed,
            account.leverage,
            account.margin_usage_pct * 100,
            self.round_trip_count,
            self.scheduler.format_uptime(),
        )

        if metrics.sharpe_capped:
            logger.warning(
                "Only %d/8 return observations — Sharpe rank capped at 50 pts if competition ended now. "
                "Need %d more 15-min intervals of active trading.",
                metrics.intervals_recorded,
                metrics.intervals_needed - metrics.intervals_recorded,
            )

    # ------------------------------------------------------------------
    # Order dispatch
    # ------------------------------------------------------------------

    def _publish_state(self, account: AccountState) -> None:
        """Push live state to the CompetitionStateBus for the web dashboard."""
        bus = self.state_bus
        bus.update_signals(self.active_signals)
        bus.update_positions(list(self.tracker.positions.values()))
        bus.update_account(account)
        bus.update_metrics(self.tracker.calculate_scoring_metrics())
        bus.set_uptime(self.scheduler.format_uptime())
        bus.set_violations(self.tracker.violations)
        bus.set_round_trip_count(self.round_trip_count)

    def _cancel_pending_for_ticker(self, ticker: str) -> None:
        """Cancel any resting limit order for *ticker* before placing a new one."""
        oid = self._open_orders.pop(ticker, None)
        if oid and oid in self._pending_limits:
            self.broker.cancel_order(oid)
            del self._pending_limits[oid]
            logger.debug("Cancelled stale limit %s for %s", oid, ticker)

    def reset_round(self) -> None:
        """Clear per-round state (violations, round-trip counter).

        Call this at the start of each competition round. Round boundaries
        will be published by the organiser — wire this to the scheduler once
        the exact times are known.
        """
        logger.info(
            "Round reset — clearing %d violations, round_trip_count=%d",
            len(self.tracker.violations), self.round_trip_count,
        )
        self.tracker.violations.clear()
        self.round_trip_count = 0
        # Cancel all pending limits so we start the new round with a clean slate
        for oid in list(self._pending_limits.keys()):
            self.broker.cancel_order(oid)
        self._pending_limits.clear()
        self._open_orders.clear()

    def _dispatch(self, order: RegulatedOrder, is_close: bool = False) -> Optional[OrderResult]:
        """Send an approved order to the broker. Returns the OrderResult or None.

        In dry-run mode the order still goes through the mock broker so
        positions are tracked and the engine doesn't re-enter the same
        ticker every polling cycle.
        """
        if self.dry_run:
            order_label = "LIMIT" if order.order_type == "LIMIT" else "MARKET"
            logger.info(
                "DRY-RUN: placing %s %s %s $%.0f (mock, position tracked)",
                order_label, order.action.value, order.ticker, order.order_size_notional,
            )
        try:
            result = self.broker.place_order(order)
            if result.status == "FILLED":
                logger.info(
                    "FILLED: %s %s %s $%.0f @ $%.5f",
                    result.order_id, result.action.value, result.ticker,
                    result.filled_size, result.filled_price or 0,
                )
                # Count completed round-trips (open fill + close fill)
                if is_close:
                    self.round_trip_count += 1
                    if self.round_trip_count % 5 == 0:
                        logger.info(
                            "Round-trips completed: %d/30 (Best Sharpe gate)",
                            self.round_trip_count,
                        )
                # Record trade for web dashboard
                if self.state_bus:
                    signal = self.active_signals.get(order.ticker)
                    self.state_bus.add_trade(TradeRecord(
                        timestamp=time.time(),
                        ticker=order.ticker,
                        action=order.action,
                        size_notional=result.filled_size,
                        fill_price=result.filled_price,
                        status=ApprovalStatus.APPROVED,
                        reason=f"Signal: {signal.action.value} (confidence={signal.confidence:.2f})" if signal else "Manual",
                        signal_confidence=signal.confidence if signal else 0,
                        analysis_excerpt=(self.state_bus.active_analysis.get(order.ticker, "") or "")[:300],
                        analysis_full=self.state_bus.active_analysis.get(order.ticker, "") or "",
                        analysis_id=signal.analysis_id if signal else None,
                        order_id=result.order_id,
                    ))
            elif result.status == "PENDING":
                logger.info(
                    "LIMIT PENDING: %s %s %s @ %.5f $%.0f",
                    result.order_id, order.action.value, order.ticker,
                    order.limit_price or 0, order.order_size_notional,
                )
            return result
        except Exception as exc:
            logger.error("Order dispatch failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _shutdown(self) -> None:
        """Log final state and clean up."""
        logger.info("Competition engine shutting down")
        try:
            account = self.broker.get_account_state()
            metrics = self.tracker.calculate_scoring_metrics()
            logger.info(
                "FINAL | Return: %+.2f%% | MaxDD: %.2f%% | Sharpe: %s | "
                "Obs: %d/%d | RoundTrips: %d | Equity: $%.0f | Positions: %d",
                metrics.total_return_pct,
                metrics.max_drawdown_pct,
                f"{metrics.sharpe_ratio:.2f}" if metrics.sharpe_ratio is not None else "N/A",
                metrics.intervals_recorded,
                metrics.intervals_needed,
                self.round_trip_count,
                account.equity,
                account.open_positions_count,
            )
            for v in self.tracker.violations:
                if v.severity.value in ("PENALTY", "DISQUALIFICATION"):
                    logger.warning("VIOLATION: [%s] %s — %s", v.severity.value, v.rule, v.detail)
        except Exception as exc:
            logger.error("Error during shutdown: %s", exc)
