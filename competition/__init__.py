# competition/__init__.py
"""Competition trading engine — TradingAgents as a signal generator behind a
strict risk-containment firewall for the June 21–24 trading competition."""

from competition.config import (
    MAX_LEVERAGE,
    MAX_MARGIN_PCT,
    POLLING_INTERVAL_S,
    DEFAULT_INSTRUMENTS,
    DEFAULT_POSITION_PCT,
)
from competition.models import (
    AccountState,
    RegulatedOrder,
    TradeSignal,
    Position,
    ApprovalResult,
    ApprovalStatus,
    OrderAction,
    OrderResult,
    EquitySnapshot,
    Violation,
    ViolationSeverity,
    ScoringMetrics,
)
from competition.risk_firewall import ExecutionEngine
from competition.api_client import AbstractBrokerClient, MockBrokerClient
from competition.signal_adapter import SignalAdapter
from competition.indicator_signals import IndicatorSignals
from competition.state_tracker import StateTracker
from competition.scheduler import Scheduler
from competition.engine import CompetitionEngine

__all__ = [
    "MAX_LEVERAGE",
    "MAX_MARGIN_PCT",
    "POLLING_INTERVAL_S",
    "DEFAULT_INSTRUMENTS",
    "DEFAULT_POSITION_PCT",
    "AccountState",
    "RegulatedOrder",
    "TradeSignal",
    "Position",
    "ApprovalResult",
    "ApprovalStatus",
    "OrderAction",
    "OrderResult",
    "EquitySnapshot",
    "Violation",
    "ViolationSeverity",
    "ScoringMetrics",
    "ExecutionEngine",
    "AbstractBrokerClient",
    "MockBrokerClient",
    "SignalAdapter",
    "IndicatorSignals",
    "StateTracker",
    "Scheduler",
    "CompetitionEngine",
]
