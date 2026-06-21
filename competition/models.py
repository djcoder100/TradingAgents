# competition/models.py
"""Pydantic models for the competition trading engine.

Every trade decision flows through these types so the risk firewall can
mathematically verify compliance before any order reaches the broker API.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ApprovalStatus(str, Enum):
    APPROVED = "APPROVED"
    MUTATED = "MUTATED"    # size capped to stay within limits
    REJECTED = "REJECTED"  # blocked entirely


class ViolationSeverity(str, Enum):
    WARNING = "WARNING"              # approaching a limit
    PENALTY = "PENALTY"              # rule triggered, points will be deducted
    DISQUALIFICATION = "DISQUALIFICATION"  # immediate removal


# ---------------------------------------------------------------------------
# Account & order models
# ---------------------------------------------------------------------------

class AccountState(BaseModel):
    """Snapshot of account metrics fetched from the broker API."""
    equity: float = Field(ge=0, description="Total account equity in USD")
    used_margin: float = Field(ge=0, description="Margin currently in use")
    gross_notional_exposure: float = Field(ge=0, description="Sum of |position notional| across all open positions")
    open_positions_count: int = Field(ge=0)
    buying_power: float = Field(ge=0, description="Available margin * leverage multiplier")

    @property
    def leverage(self) -> float:
        """Current leverage ratio."""
        return self.gross_notional_exposure / self.equity if self.equity > 0 else 0.0

    @property
    def margin_usage_pct(self) -> float:
        """Used margin as a fraction of equity."""
        return self.used_margin / self.equity if self.equity > 0 else 0.0


class RegulatedOrder(BaseModel):
    """An order that MUST pass through the ExecutionEngine before dispatch."""
    action: OrderAction = Field(description="BUY, SELL, or HOLD")
    ticker: str = Field(min_length=1, description="Competition instrument ticker, e.g. XAUUSD")
    order_size_notional: float = Field(gt=0, description="Notional size in USD")
    order_type: str = Field(default="MARKET", description="MARKET or LIMIT")
    limit_price: Optional[float] = Field(None, description="Limit price; required when order_type=LIMIT")

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v: object) -> OrderAction:
        if isinstance(v, OrderAction):
            return v
        try:
            return OrderAction(str(v).upper())
        except (ValueError, TypeError):
            return OrderAction.HOLD


class ApprovalResult(BaseModel):
    """Verdict from the risk firewall."""
    status: ApprovalStatus
    reason: str = ""
    safe_size: Optional[float] = None  # populated when MUTATED


class TradeSignal(RegulatedOrder):
    """A RegulatedOrder enriched with entry/exit targets and metadata."""
    entry_price_target: Optional[float] = Field(None, description="Ideal entry price in quote currency")
    stop_loss: Optional[float] = Field(None, description="Hard stop-loss price")
    take_profit: Optional[float] = Field(None, description="Take-profit price target")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="0.0–1.0 signal conviction")
    created_at: float = Field(default_factory=time.time, description="Unix timestamp when the signal was generated")
    expires_at: float = Field(default_factory=lambda: time.time() + 1800, description="Unix timestamp after which the signal is stale")
    analysis_id: Optional[str] = Field(None, description="ID of the TA pipeline run that produced this signal")

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def age_s(self) -> float:
        return time.time() - self.created_at


class Position(BaseModel):
    """An open position tracked locally (synced from broker)."""
    ticker: str
    size_notional: float = Field(description="Absolute notional value of the position in USD")
    direction: OrderAction = Field(description="BUY = long, SELL = short")
    avg_entry_price: float
    current_px: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    opened_at: float = Field(default_factory=time.time)


class OrderResult(BaseModel):
    """Result of placing an order through the broker API."""
    order_id: str
    status: str  # FILLED, PARTIAL, REJECTED, PENDING
    ticker: str
    action: OrderAction
    filled_size: float
    filled_price: Optional[float] = None
    timestamp: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Tracking & compliance models
# ---------------------------------------------------------------------------

class EquitySnapshot(BaseModel):
    """Recorded every 15 minutes for Sharpe / Return / MaxDD calculation."""
    timestamp: float = Field(default_factory=time.time)
    equity: float
    leverage: float
    margin_pct: float
    return_vs_prev: Optional[float] = None  # None on first snapshot of the day


class Violation(BaseModel):
    """A compliance rule breach detected by the firewall."""
    severity: ViolationSeverity
    rule: str = Field(description="Which rule was violated, e.g. 'leverage > 28x'")
    detail: str = ""
    detected_at: float = Field(default_factory=time.time)
    current_value: float = Field(description="The metric value that triggered the violation")


class TradeRecord(BaseModel):
    """A completed trade with the analysis that produced it."""
    timestamp: float = Field(default_factory=time.time)
    ticker: str
    action: OrderAction
    size_notional: float
    fill_price: Optional[float] = None
    status: ApprovalStatus = ApprovalStatus.APPROVED
    reason: str = ""                              # why the trade was made
    signal_confidence: float = 0.0
    analysis_excerpt: str = ""                    # first ~300 chars of PM decision
    analysis_full: str = ""                       # full markdown of the TA decision
    analysis_id: Optional[str] = None            # ID of the TA pipeline run
    order_id: str = ""


class ScoringMetrics(BaseModel):
    """Live estimate of competition scoring dimensions."""
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: Optional[float] = None  # None if <2 snapshots
    intervals_recorded: int = 0
    intervals_needed: int = 8
    sharpe_capped: bool = False  # True if <8 intervals → max 50 points for Sharpe
