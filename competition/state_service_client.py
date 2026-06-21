"""
Client for writing state updates to the state service.

Used by the engine to publish state changes that both the engine and
web frontend can read.
"""

import logging
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StateServiceClient:
    """Client for posting state updates to the state service."""

    def __init__(self, service_url: str = "http://localhost:9000"):
        self.service_url = service_url
        self.available = False
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if state service is running."""
        try:
            resp = requests.get(f"{self.service_url}/api/health", timeout=1)
            self.available = resp.status_code == 200
            if self.available:
                logger.info(f"✓ State service available at {self.service_url}")
            else:
                logger.warning(f"State service not responding at {self.service_url}")
        except Exception as e:
            logger.debug(f"State service unavailable: {e}")
            self.available = False

    def update_signals(self, signals: Dict[str, Any]) -> bool:
        """Post signals update to state service."""
        if not self.available:
            return False
        try:
            requests.post(
                f"{self.service_url}/api/competition/state/update",
                params={"key": "signals"},
                json=signals,
                timeout=2,
            )
            return True
        except Exception as e:
            logger.debug(f"Failed to post signals: {e}")
            return False

    def update_analysis_progress(self, ticker: str, progress: Dict[str, Any]) -> bool:
        """Post analysis progress update."""
        if not self.available:
            return False
        try:
            requests.post(
                f"{self.service_url}/api/competition/state/merge",
                json={"analysis_progress": {ticker: progress}},
                timeout=2,
            )
            return True
        except Exception as e:
            logger.debug(f"Failed to post analysis progress: {e}")
            return False

    def update_trades(self, trades: list) -> bool:
        """Post trade history update."""
        if not self.available:
            return False
        try:
            requests.post(
                f"{self.service_url}/api/competition/state/update",
                params={"key": "trades"},
                json=trades,
                timeout=2,
            )
            return True
        except Exception as e:
            logger.debug(f"Failed to post trades: {e}")
            return False

    def update_full_analysis(self, analysis_id: str, data: Dict[str, Any]) -> bool:
        """Post full analysis update."""
        if not self.available:
            return False
        try:
            requests.post(
                f"{self.service_url}/api/competition/state/merge",
                json={"full_analysis": {analysis_id: data}},
                timeout=2,
            )
            return True
        except Exception as e:
            logger.debug(f"Failed to post full analysis: {e}")
            return False

    def merge_state(self, updates: Dict[str, Any]) -> bool:
        """Post arbitrary state updates (merge)."""
        if not self.available:
            return False
        try:
            requests.post(
                f"{self.service_url}/api/competition/state/merge",
                json=updates,
                timeout=2,
            )
            return True
        except Exception as e:
            logger.debug(f"Failed to merge state: {e}")
            return False
