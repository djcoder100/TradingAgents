# competition/risk_firewall.py
"""ExecutionEngine — the unbreakable rule engine.

Every trade decision the agent produces MUST pass through this firewall
BEFORE dispatch to the broker API.  It enforces the competition's §13
Risk Discipline rules mathematically, with no discretion left to the LLM.

Leverage guard: cap at 25x (stricter than the 28x penalty threshold).
Margin guard:  block when projected usage exceeds 80% (stricter than 90%).
Compliance:    alert on 28x / 30x / 90% breaches for audit trail.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from competition.models import (
    AccountState,
    RegulatedOrder,
    ApprovalResult,
    ApprovalStatus,
    OrderAction,
    Position,
    Violation,
    ViolationSeverity,
)
from competition.config import (
    MAX_LEVERAGE,
    MAX_MARGIN_PCT,
    LEVERAGE_PENALTY,
    LEVERAGE_DISQUALIFY,
    MARGIN_PENALTY_PCT,
    MARGIN_PENALTY_DURATION_S,
)

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Intercepts every order and forces compliance with competition rules."""

    def __init__(
        self,
        max_leverage_limit: float = MAX_LEVERAGE,
        max_margin_pct: float = MAX_MARGIN_PCT,
    ):
        self.max_leverage_limit = max_leverage_limit
        self.max_margin_pct = max_margin_pct

    # ------------------------------------------------------------------
    # Pre-trade guard (called on every proposed order)
    # ------------------------------------------------------------------

    def verify_and_route(
        self, order: RegulatedOrder, account: AccountState
    ) -> ApprovalResult:
        """Validate a proposed order against leverage and margin limits.

        Returns APPROVED (safe to send), MUTATED (size capped to safe
        level), or REJECTED (blocked entirely).
        """
        if order.action == OrderAction.HOLD:
            return ApprovalResult(
                status=ApprovalStatus.REJECTED,
                reason="Agent placed manual HOLD — no trade to execute.",
            )

        # Projected leverage after this trade fills
        projected_exposure = account.gross_notional_exposure + order.order_size_notional
        projected_leverage = (
            projected_exposure / account.equity if account.equity > 0 else float("inf")
        )

        # Rule 13.2: Leverage guardrail
        if projected_leverage > self.max_leverage_limit:
            safe_size = order.order_size_notional * (
                self.max_leverage_limit / projected_leverage
            )
            return ApprovalResult(
                status=ApprovalStatus.MUTATED,
                reason=(
                    f"Leverage limit exceeded "
                    f"(projected {projected_leverage:.2f}x > {self.max_leverage_limit}x). "
                    f"Capping trade size to ${safe_size:,.0f}."
                ),
                safe_size=safe_size,
            )

        # Rule 13.1: Margin usage guardrail
        projected_margin_usage = (
            account.used_margin / account.equity if account.equity > 0 else 1.0
        )
        if projected_margin_usage > self.max_margin_pct:
            return ApprovalResult(
                status=ApprovalStatus.REJECTED,
                reason=(
                    f"Margin usage too high "
                    f"({projected_margin_usage * 100:.1f}% > {self.max_margin_pct * 100:.0f}%). "
                    f"Order blocked to preserve risk points."
                ),
            )

        return ApprovalResult(
            status=ApprovalStatus.APPROVED,
            reason="All risk checks passed.",
            safe_size=order.order_size_notional,
        )

    # ------------------------------------------------------------------
    # Post-trade compliance audit (called every 15 min)
    # ------------------------------------------------------------------

    def check_compliance(
        self,
        account: AccountState,
        positions: list[Position],
        leverage_history: Optional[list[tuple[float, float]]] = None,
        margin_history: Optional[list[tuple[float, float]]] = None,
    ) -> list[Violation]:
        """Audit current state against competition red-line thresholds.

        *leverage_history*: list of (timestamp, leverage) samples.
        *margin_history*:   list of (timestamp, margin_pct) samples.
        """
        violations: list[Violation] = []

        current_leverage = account.leverage
        current_margin = account.margin_usage_pct

        # --- Leverage checks ---
        if current_leverage > LEVERAGE_DISQUALIFY:
            violations.append(
                Violation(
                    severity=ViolationSeverity.DISQUALIFICATION,
                    rule=f"leverage > {LEVERAGE_DISQUALIFY}x",
                    detail=(
                        f"Current leverage is {current_leverage:.2f}x. "
                        f"IMMEDIATE DISQUALIFICATION per competition rules."
                    ),
                    current_value=current_leverage,
                )
            )
        elif current_leverage > LEVERAGE_PENALTY:
            violations.append(
                Violation(
                    severity=ViolationSeverity.PENALTY,
                    rule=f"leverage > {LEVERAGE_PENALTY}x",
                    detail=(
                        f"Current leverage is {current_leverage:.2f}x. "
                        f"20-point deduction applies."
                    ),
                    current_value=current_leverage,
                )
            )

        # --- Margin checks (duration-aware) ---
        if current_margin > MARGIN_PENALTY_PCT:
            # Check if it's been sustained for >30 min
            sustained = False
            if margin_history:
                sustained_duration = self._duration_above_threshold(
                    margin_history, MARGIN_PENALTY_PCT
                )
                sustained = sustained_duration >= MARGIN_PENALTY_DURATION_S

            severity = (
                ViolationSeverity.PENALTY if sustained else ViolationSeverity.WARNING
            )
            detail = (
                f"Margin usage at {current_margin * 100:.1f}%. "
                f"{'Sustained >30 min — 20-point deduction applies.' if sustained else 'Approaching penalty threshold.'}"
            )
            violations.append(
                Violation(
                    severity=severity,
                    rule=f"margin > {MARGIN_PENALTY_PCT * 100:.0f}%",
                    detail=detail,
                    current_value=current_margin,
                )
            )

        # --- Position concentration check (soft warning) ---
        if positions and len(positions) > 8:
            largest_pct = max(
                (p.size_notional / account.equity for p in positions),
                default=0,
            )
            if largest_pct > 0.25:
                violations.append(
                    Violation(
                        severity=ViolationSeverity.WARNING,
                        rule="position concentration",
                        detail=f"Largest position is {largest_pct * 100:.1f}% of equity.",
                        current_value=largest_pct,
                    )
                )

        return violations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _duration_above_threshold(
        history: list[tuple[float, float]], threshold: float
    ) -> float:
        """Return the longest continuous duration (seconds) spent above *threshold*.

        *history*: list of (timestamp_unix, metric_value) sorted by time ascending.
        """
        if not history:
            return 0.0
        max_duration = 0.0
        started_at: Optional[float] = None
        for ts, val in history:
            if val > threshold:
                if started_at is None:
                    started_at = ts
                else:
                    max_duration = max(max_duration, ts - started_at)
            else:
                if started_at is not None:
                    max_duration = max(max_duration, ts - started_at)
                    started_at = None
        # Don't forget an ongoing breach
        if started_at is not None:
            now = time.time()
            max_duration = max(max_duration, now - started_at)
        return max_duration
