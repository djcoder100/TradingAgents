# competition/state_bus.py
"""Thread-safe state bus shared between the competition engine and web API.

The engine writes its live state here every polling tick.  The web API
reads from it on each request — no database, no IPC, just a simple
in-process singleton.  Both sides run in the same process when started
with ``--web``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

from competition.models import (
    TradeSignal,
    Position,
    TradeRecord,
    AccountState,
    ScoringMetrics,
)

logger = logging.getLogger(__name__)

# Try to import state service client (optional, falls back to disk-only if service unavailable)
try:
    from competition.state_service_client import StateServiceClient
    HAS_STATE_SERVICE = True
except ImportError:
    HAS_STATE_SERVICE = False
    StateServiceClient = None


class CompetitionStateBus:
    """Singleton state holder.  Write from engine thread, read from asyncio."""

    _instance: Optional[CompetitionStateBus] = None
    _lock = threading.Lock()

    def __new__(cls) -> CompetitionStateBus:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._rwlock = threading.RLock()
        self.signals: dict[str, TradeSignal] = {}
        self.positions: list[Position] = []
        self.trade_history: list[TradeRecord] = []
        self.account: Optional[AccountState] = None
        self.metrics: Optional[ScoringMetrics] = None
        self.active_analysis: dict[str, str] = {}  # ticker → latest PM markdown
        self.analysis_progress: dict[str, dict] = {}  # ticker → {stage, step, total, started_at, elapsed_s}
        self.full_analysis: dict[str, dict] = {}          # analysis_id → AnalysisResultResponse dict
        self.latest_analysis_id: dict[str, str] = {}      # ticker → latest analysis_id
        self.last_updated: float = 0.0
        self.uptime: str = "00:00:00"
        self.violations: list = []
        self.round_trip_count: int = 0  # Best Sharpe gate: need ≥30

        # Persistence
        self._state_dir = Path.home() / ".tradingagents"
        self._trade_history_path = self._state_dir / "trade_history.json"
        self._full_analysis_path = self._state_dir / "full_analysis.json"
        self._active_analysis_path = self._state_dir / "active_analysis.json"
        self._analysis_progress_path = self._state_dir / "analysis_progress.json"
        self._load_trade_history()
        self._load_full_analysis()
        self._load_active_analysis()
        self._load_analysis_progress()

        # State service client (optional, for cloud deployment)
        self._state_service: Optional[StateServiceClient] = None
        if HAS_STATE_SERVICE:
            service_url = os.environ.get("COMPETITION_STATE_SERVICE_URL", "http://localhost:9000")
            self._state_service = StateServiceClient(service_url)
            if self._state_service.available:
                logger.info(f"State service enabled at {service_url}")

    # ------------------------------------------------------------------
    # Persistence (trade history survives across engine restarts)
    # ------------------------------------------------------------------

    def _load_trade_history(self) -> None:
        """Load persisted trade history from disk if it exists."""
        if not self._trade_history_path.exists():
            return
        try:
            with open(self._trade_history_path, "r") as f:
                data = json.load(f)
            self.trade_history = [TradeRecord(**t) for t in data]
            logger.info(f"Loaded {len(self.trade_history)} trades from {self._trade_history_path}")
        except Exception as e:
            logger.error(f"Failed to load trade history: {e}")

    def _save_trade_history(self) -> None:
        """Persist trade history to disk."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            with open(self._trade_history_path, "w") as f:
                json.dump(
                    [json.loads(t.model_dump_json()) for t in self.trade_history[-500:]],
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Failed to save trade history: {e}")

    def _load_full_analysis(self) -> None:
        """Load persisted full analysis from disk if it exists."""
        if not self._full_analysis_path.exists():
            return
        try:
            with open(self._full_analysis_path, "r") as f:
                self.full_analysis = json.load(f)
            logger.info(f"Loaded {len(self.full_analysis)} full analyses from disk")
        except Exception as e:
            logger.error(f"Failed to load full analysis: {e}")

    def _save_full_analysis(self) -> None:
        """Persist full analysis to disk."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            with open(self._full_analysis_path, "w") as f:
                json.dump(self.full_analysis, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save full analysis: {e}")

    def _load_active_analysis(self) -> None:
        """Load persisted active analysis (latest markdown per ticker) from disk if it exists."""
        if not self._active_analysis_path.exists():
            return
        try:
            with open(self._active_analysis_path, "r") as f:
                self.active_analysis = json.load(f)
            logger.info(f"Loaded {len(self.active_analysis)} active analyses from disk")
        except Exception as e:
            logger.error(f"Failed to load active analysis: {e}")

    def _save_active_analysis(self) -> None:
        """Persist active analysis markdown to disk."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            with open(self._active_analysis_path, "w") as f:
                json.dump(self.active_analysis, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save active analysis: {e}")

    def _load_analysis_progress(self) -> None:
        """Load persisted analysis progress from disk if it exists."""
        if not self._analysis_progress_path.exists():
            return
        try:
            with open(self._analysis_progress_path, "r") as f:
                self.analysis_progress = json.load(f)
            logger.info(f"Loaded {len(self.analysis_progress)} active analyses from disk")
        except Exception as e:
            logger.error(f"Failed to load analysis progress: {e}")

    def _save_analysis_progress(self) -> None:
        """Persist analysis progress to disk (for web-only dashboards to read)."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            with open(self._analysis_progress_path, "w") as f:
                json.dump(self.analysis_progress, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analysis progress: {e}")

    # ------------------------------------------------------------------
    # Atomic snapshot (readers get a consistent copy)
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Return a consistent dict snapshot for the web API."""
        with self._rwlock:
            return {
                "signals": [
                    {
                        "ticker": t,
                        "action": s.action.value,
                        "confidence": s.confidence,
                        "order_size_notional": s.order_size_notional,
                        "entry_price_target": s.entry_price_target,
                        "stop_loss": s.stop_loss,
                        "take_profit": s.take_profit,
                        "created_at": s.created_at,
                        "expires_at": s.expires_at,
                        "is_expired": s.is_expired(),
                        "analysis": self.active_analysis.get(t, ""),
                        "analysis_id": s.analysis_id or self.latest_analysis_id.get(t.upper()),
                    }
                    for t, s in self.signals.items()
                ],
                "positions": [
                    {
                        "ticker": p.ticker,
                        "direction": p.direction.value,
                        "size_notional": p.size_notional,
                        "avg_entry_price": p.avg_entry_price,
                        "current_px": p.current_px,
                        "unrealized_pnl": p.unrealized_pnl,
                        "opened_at": p.opened_at,
                    }
                    for p in self.positions
                ],
                "trades": [
                    {
                        "timestamp": t.timestamp,
                        "ticker": t.ticker,
                        "action": t.action.value,
                        "size_notional": t.size_notional,
                        "fill_price": t.fill_price,
                        "status": t.status.value,
                        "reason": t.reason,
                        "signal_confidence": t.signal_confidence,
                        "analysis_excerpt": t.analysis_excerpt,
                        "analysis_full": t.analysis_full,
                        "analysis_id": t.analysis_id or self.latest_analysis_id.get(t.ticker.upper()),
                        "order_id": t.order_id,
                    }
                    for t in self.trade_history[-50:]  # last 50 trades
                ],
                "account": {
                    "equity": self.account.equity,
                    "used_margin": self.account.used_margin,
                    "leverage": self.account.leverage,
                    "margin_usage_pct": self.account.margin_usage_pct,
                    "open_positions_count": self.account.open_positions_count,
                } if self.account else None,
                "metrics": {
                    "total_return_pct": self.metrics.total_return_pct,
                    "max_drawdown_pct": self.metrics.max_drawdown_pct,
                    "sharpe_ratio": self.metrics.sharpe_ratio,
                    "intervals_recorded": self.metrics.intervals_recorded,
                    "intervals_needed": self.metrics.intervals_needed,
                    "sharpe_capped": self.metrics.sharpe_capped,
                } if self.metrics else None,
                "analysis_progress": {
                    t: {**p, "elapsed_s": time.time() - p["started_at"]}
                    for t, p in self.analysis_progress.items()
                },
                "last_updated": self.last_updated,
                "uptime": self.uptime,
                "round_trip_count": self.round_trip_count,
                "violations": [
                    {"severity": v.severity.value, "rule": v.rule, "detail": v.detail}
                    for v in self.violations[-10:]  # last 10
                ],
            }

    # ------------------------------------------------------------------
    # Writers (called from engine thread)
    # ------------------------------------------------------------------

    def update_signals(self, signals: dict[str, TradeSignal]) -> None:
        with self._rwlock:
            self.signals = dict(signals)
            self.last_updated = time.time()
        # Post to state service if available
        if self._state_service:
            signal_data = {t: {"ticker": s.ticker, "action": s.action.value, "confidence": s.confidence,
                               "order_size_notional": s.order_size_notional, "created_at": s.created_at,
                               "expires_at": s.expires_at, "analysis_id": s.analysis_id}
                          for t, s in signals.items()}
            self._state_service.update_signals(signal_data)

    def update_positions(self, positions: list[Position]) -> None:
        with self._rwlock:
            self.positions = list(positions)
            self.last_updated = time.time()

    def add_trade(self, trade: TradeRecord) -> None:
        with self._rwlock:
            self.trade_history.append(trade)
            # Keep at most 500 trades in memory
            if len(self.trade_history) > 500:
                self.trade_history = self.trade_history[-500:]
            self.last_updated = time.time()
        # Persist to disk (outside lock to avoid blocking)
        self._save_trade_history()
        # Post to state service if available
        if self._state_service:
            trade_data = [json.loads(t.model_dump_json()) for t in self.trade_history[-500:]]
            self._state_service.update_trades(trade_data)

    def update_account(self, account: AccountState) -> None:
        with self._rwlock:
            self.account = account
            self.last_updated = time.time()

    def update_metrics(self, metrics: ScoringMetrics) -> None:
        with self._rwlock:
            self.metrics = metrics
            self.last_updated = time.time()

    def set_analysis(self, ticker: str, markdown: str) -> None:
        with self._rwlock:
            self.active_analysis[ticker] = markdown
            self.last_updated = time.time()
        # Persist to disk (outside lock)
        self._save_active_analysis()
        # Post to state service if available
        if self._state_service:
            self._state_service.merge_state({"active_analysis": {ticker: markdown}})

    def set_analysis_progress(self, ticker: str, stage: str, step: int, total: int, started_at: float) -> None:
        with self._rwlock:
            self.analysis_progress[ticker] = {
                "stage": stage,
                "step": step,
                "total": total,
                "started_at": started_at,
            }
        # Persist to disk (outside lock) so web-only dashboards can see live progress
        self._save_analysis_progress()
        # Post to state service if available (for live dashboard updates)
        if self._state_service:
            progress = {"stage": stage, "step": step, "total": total, "started_at": started_at}
            self._state_service.update_analysis_progress(ticker, progress)

    def clear_analysis_progress(self, ticker: str) -> None:
        with self._rwlock:
            self.analysis_progress.pop(ticker, None)
        # Persist to disk
        self._save_analysis_progress()

    def set_full_analysis(self, analysis_id: str, data: dict) -> None:
        with self._rwlock:
            self.full_analysis[analysis_id] = data
            ticker = data.get("ticker", "")
            if ticker:
                self.latest_analysis_id[ticker.upper()] = analysis_id
            self.last_updated = time.time()
        # Persist to disk (outside lock)
        self._save_full_analysis()
        # Post to state service if available
        if self._state_service:
            self._state_service.update_full_analysis(analysis_id, data)

    def get_full_analysis(self, analysis_id: str) -> Optional[dict]:
        """Fetch by analysis_id; also accepts a ticker to return its latest analysis."""
        with self._rwlock:
            if analysis_id in self.full_analysis:
                return self.full_analysis[analysis_id]
            # Fallback: treat as ticker and return the most recent analysis
            resolved = self.latest_analysis_id.get(analysis_id.upper())
            if resolved:
                return self.full_analysis.get(resolved)
            return None

    def set_round_trip_count(self, count: int) -> None:
        with self._rwlock:
            self.round_trip_count = count

    def set_uptime(self, uptime: str) -> None:
        with self._rwlock:
            self.uptime = uptime

    def set_violations(self, violations: list) -> None:
        with self._rwlock:
            self.violations = list(violations)
