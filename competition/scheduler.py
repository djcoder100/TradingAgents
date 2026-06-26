# competition/scheduler.py
"""Simple time-based scheduler for the competition engine loop.

Manages: when to poll, when to refresh TradingAgents signals,
when to record 15-min snapshots, and when to check compliance.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from competition.config import (
    POLLING_INTERVAL_S,
    SIGNAL_REFRESH_INTERVAL_S,
    COMPETITION_END,
    DAY_TRADING_CLOSE_EOD,
    DAY_TRADING_EOD_BUFFER_MIN,
)


class Scheduler:
    """Drives the cadence of the competition engine."""

    def __init__(
        self,
        polling_interval_s: float = POLLING_INTERVAL_S,
        signal_refresh_interval_s: float = SIGNAL_REFRESH_INTERVAL_S,
    ):
        self.polling_interval_s = polling_interval_s
        self.signal_refresh_interval_s = signal_refresh_interval_s
        self._last_signal_refresh = 0.0
        self._start_time = time.time()
        self._competition_end = datetime.fromisoformat(COMPETITION_END).timestamp()

    # ------------------------------------------------------------------
    # Timing decisions
    # ------------------------------------------------------------------

    @property
    def elapsed_s(self) -> float:
        return time.time() - self._start_time

    def is_competition_active(self) -> bool:
        """Return False when the competition window has closed."""
        return time.time() < self._competition_end

    def should_refresh_signals(self) -> bool:
        """True when it's time to re-run TradingAgents on top instruments."""
        now = time.time()
        if now - self._last_signal_refresh >= self.signal_refresh_interval_s:
            self._last_signal_refresh = now
            return True
        return False

    @staticmethod
    def is_15min_boundary() -> bool:
        """True when the current minute is on a 15-min boundary (:00, :15, :30, :45)."""
        now = time.localtime()
        return now.tm_min % 15 == 0 and now.tm_sec < 10

    @staticmethod
    def sleep_until_next_tick() -> None:
        """Sleep for the configured polling interval."""
        time.sleep(POLLING_INTERVAL_S)

    # ------------------------------------------------------------------
    # Day-trading (EOD close) logic
    # ------------------------------------------------------------------

    @staticmethod
    def should_close_all_positions() -> bool:
        """Check if it's time to liquidate all positions (day-trading EOD).

        For Forex: market closes Friday 5pm EST, Sunday 5pm EST.
        For US stocks: market closes 4pm EST (Mon-Fri).
        For now, use a simple heuristic: close before 4pm EST.
        """
        if not DAY_TRADING_CLOSE_EOD:
            return False

        now = datetime.now(timezone.utc)
        # Convert to EST (UTC-5) for market hours
        now_est = now.astimezone()

        # Check if we're within close buffer (default: 10 min before 4pm = 3:50pm)
        close_hour = 16  # 4pm EST
        close_min = 0
        buffer_min = DAY_TRADING_EOD_BUFFER_MIN

        # Market close time: 3:50pm EST (10 min before 4pm)
        close_buffer_time = now_est.replace(hour=close_hour, minute=close_min)
        close_buffer_time = close_buffer_time.replace(
            hour=close_hour - 1,
            minute=60 - buffer_min,
            second=0,
            microsecond=0
        )

        # If current time >= 3:50pm EST, close positions
        if now_est >= close_buffer_time:
            return True

        return False

    @staticmethod
    def position_exceeded_max_hold(position_opened_at: float) -> bool:
        """Check if a position has been held longer than max_hold_minutes.

        Args:
            position_opened_at: Unix timestamp when position was opened

        Returns:
            True if position age > max_hold_minutes
        """
        from competition.config import DAY_TRADING_MAX_HOLD_MIN

        position_age_s = time.time() - position_opened_at
        position_age_min = position_age_s / 60.0

        return position_age_min > DAY_TRADING_MAX_HOLD_MIN

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def format_uptime(self) -> str:
        elapsed = self.elapsed_s
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def time_remaining_s(self) -> float:
        return max(0.0, self._competition_end - time.time())
