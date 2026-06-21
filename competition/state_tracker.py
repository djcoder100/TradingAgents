# competition/state_tracker.py
"""Position tracking, equity snapshots, and compliance monitoring.

Maintains the ground-truth picture of the account so the engine can:
- Sync open positions with the broker
- Record equity snapshots every 15 min (§7 Sharpe requirement)
- Compute live Return / MaxDD / Sharpe estimates
- Monitor for competition rule violations
"""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

from competition.models import (
    AccountState,
    Position,
    EquitySnapshot,
    ScoringMetrics,
    Violation,
)
from competition.config import MIN_15MIN_INTERVALS
from competition.risk_firewall import ExecutionEngine

logger = logging.getLogger(__name__)


class StateTracker:
    """Central state holder for the competition engine."""

    def __init__(self, firewall: ExecutionEngine):
        self.firewall = firewall
        self.positions: dict[str, Position] = {}  # position_id → Position
        self.snapshots: list[EquitySnapshot] = []
        self.leverage_history: list[tuple[float, float]] = []  # (ts, leverage)
        self.margin_history: list[tuple[float, float]] = []     # (ts, margin_pct)
        self.violations: list[Violation] = []
        self._last_snapshot_minute = -1

    # ------------------------------------------------------------------
    # Update cycle (called every polling tick)
    # ------------------------------------------------------------------

    def update(
        self,
        account: AccountState,
        broker_positions: list[Position],
        prices: dict[str, float],
    ) -> None:
        """Sync state with latest broker data."""
        # Update positions — mark any no longer at broker as closed
        broker_ids = set()
        for bp in broker_positions:
            # Use ticker + size as approximate key (mock broker uses order_id;
            # real broker would have a position_id)
            key = f"{bp.ticker}:{bp.direction.value}:{bp.size_notional:.0f}"
            broker_ids.add(key)
            if key not in self.positions:
                self.positions[key] = bp
            else:
                # Update unrealized PnL
                px = prices.get(bp.ticker, bp.avg_entry_price)
                self.positions[key].current_px = px
                if bp.direction.value == "BUY":
                    self.positions[key].unrealized_pnl = (
                        (px - bp.avg_entry_price) / bp.avg_entry_price * bp.size_notional
                    )
                else:
                    self.positions[key].unrealized_pnl = (
                        (bp.avg_entry_price - px) / bp.avg_entry_price * bp.size_notional
                    )

        # Remove positions that are no longer at the broker
        for key in list(self.positions.keys()):
            if key not in broker_ids:
                logger.info("Position closed: %s", key)
                del self.positions[key]

        # Record leverage + margin history for compliance
        now = time.time()
        self.leverage_history.append((now, account.leverage))
        self.margin_history.append((now, account.margin_usage_pct))

        # Prune history older than 1 hour (keep memory bounded)
        cutoff = now - 3600
        self.leverage_history = [
            (ts, v) for ts, v in self.leverage_history if ts > cutoff
        ]
        self.margin_history = [
            (ts, v) for ts, v in self.margin_history if ts > cutoff
        ]

    # ------------------------------------------------------------------
    # 15-minute equity snapshots (§7 compliance)
    # ------------------------------------------------------------------

    def maybe_record_snapshot(self, account: AccountState, force: bool = False) -> bool:
        """Record an equity snapshot if we're on a 15-min boundary (or *force*).

        Returns True if a snapshot was recorded this tick.
        """
        now = time.localtime()
        current_minute_block = now.tm_min // 15

        if not force and current_minute_block == self._last_snapshot_minute:
            return False

        # Don't record duplicate snapshots within the same 15-min block
        # unless forced (e.g., end of day).
        if not force and len(self.snapshots) > 0:
            last_ts = self.snapshots[-1].timestamp
            if time.time() - last_ts < 14 * 60:  # within 14 min of last
                return False

        prev_equity = self.snapshots[-1].equity if self.snapshots else account.equity
        ret = (
            (account.equity - prev_equity) / prev_equity
            if prev_equity > 0
            else None
        )

        snapshot = EquitySnapshot(
            timestamp=time.time(),
            equity=account.equity,
            leverage=account.leverage,
            margin_pct=account.margin_usage_pct,
            return_vs_prev=ret,
        )
        self.snapshots.append(snapshot)
        self._last_snapshot_minute = current_minute_block

        logger.info(
            "15-min snapshot #%d: equity=$%.0f leverage=%.1fx margin=%.1f%% return=%.4f%%",
            len(self.snapshots),
            account.equity,
            account.leverage,
            account.margin_usage_pct * 100,
            (ret or 0) * 100,
        )
        return True

    # ------------------------------------------------------------------
    # Compliance check (called every 15 min)
    # ------------------------------------------------------------------

    def check_compliance(self, account: AccountState) -> list[Violation]:
        """Run the firewall compliance audit and accumulate violations."""
        new_violations = self.firewall.check_compliance(
            account,
            list(self.positions.values()),
            leverage_history=self.leverage_history,
            margin_history=self.margin_history,
        )
        self.violations.extend(new_violations)
        for v in new_violations:
            logger.warning(
                "COMPLIANCE: [%s] %s: %s",
                v.severity.value, v.rule, v.detail,
            )
        return new_violations

    # ------------------------------------------------------------------
    # Scoring metrics (live estimate)
    # ------------------------------------------------------------------

    def calculate_scoring_metrics(self) -> ScoringMetrics:
        """Compute current Return, MaxDD, and Sharpe from equity snapshots."""
        n = len(self.snapshots)
        if n < 2:
            return ScoringMetrics(intervals_recorded=0, intervals_needed=MIN_15MIN_INTERVALS)

        equities = [s.equity for s in self.snapshots]
        initial = equities[0]

        # Total return
        total_return = (equities[-1] - initial) / initial if initial > 0 else 0.0

        # Max drawdown
        peak = initial
        max_dd = 0.0
        for eq in equities:
            peak = max(peak, eq)
            dd = (peak - eq) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        # Sharpe ratio (from per-period returns)
        # First snapshot has no return (it is the baseline); returns start at snapshot 2.
        # The rule requires 8 *return* observations, which means 9 total snapshots.
        returns = [s.return_vs_prev for s in self.snapshots if s.return_vs_prev is not None]
        sharpe: Optional[float] = None
        sharpe_capped = len(returns) < MIN_15MIN_INTERVALS  # <8 returns → rank capped at 50pts
        if len(returns) >= 2:
            mean_ret = sum(returns) / len(returns)
            var = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
            if var > 0:
                # MoMQ rules §7: raw (non-annualised) ratio = Mean(r) / Std(r)
                sharpe = mean_ret / math.sqrt(var)
            else:
                sharpe = 0.0

        return ScoringMetrics(
            total_return_pct=total_return * 100,
            max_drawdown_pct=max_dd * 100,
            sharpe_ratio=sharpe,
            intervals_recorded=len(returns),   # return observations (not raw snapshot count)
            intervals_needed=MIN_15MIN_INTERVALS,
            sharpe_capped=sharpe_capped,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_active_tickers(self) -> list[str]:
        """Return tickers with currently open positions."""
        return list({p.ticker for p in self.positions.values()})

    def has_position_for(self, ticker: str) -> bool:
        """Return True if we already have an open position for *ticker*."""
        return any(p.ticker == ticker for p in self.positions.values())

    def position_count(self) -> int:
        return len(self.positions)
