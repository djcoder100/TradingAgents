"""In-memory task registry and lifecycle management.

Tasks are purely in-memory. Completed results are persisted to disk by the
core library's _log_state(). On server restart, in-flight tasks are lost;
completed results remain on disk and are accessible via the history API.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections import OrderedDict
from typing import Dict, Optional

from web.services.analysis_runner import AnalysisTask


class TaskManager:
    """Manages the lifecycle of background analysis tasks."""

    def __init__(self, ttl_seconds: int = 3600):
        self._tasks: Dict[str, AnalysisTask] = OrderedDict()
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def create_task(self, params: dict) -> AnalysisTask:
        """Create a new task, spawn its background thread, and return it."""
        task_id = str(uuid.uuid4())
        task = AnalysisTask(task_id, params)

        with self._lock:
            # Enforce TTL: prune expired completed tasks before adding
            self._prune_expired()
            self._tasks[task_id] = task

        # Start the background thread
        thread = threading.Thread(
            target=task.run_in_thread,
            name=f"analysis-{task_id[:8]}",
            daemon=True,
        )
        thread.start()
        return task

    def get_task(self, task_id: str) -> Optional[AnalysisTask]:
        """Return a task by ID, or None if unknown."""
        with self._lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Signal a running task to cancel at the next chunk boundary."""
        task = self.get_task(task_id)
        if task is None:
            return False
        task.cancel()
        return True

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the registry."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
        return False

    def _prune_expired(self) -> None:
        """Drop completed tasks older than TTL."""
        import time

        now = time.time()
        expired = []
        for task_id, task in self._tasks.items():
            if task.status in ("completed", "failed", "cancelled"):
                if task.completed_at and (now - task.completed_at) > self._ttl:
                    expired.append(task_id)

        for task_id in expired:
            del self._tasks[task_id]

    def shutdown(self) -> None:
        """Cancel all running tasks and clear the registry."""
        with self._lock:
            for task in list(self._tasks.values()):
                if task.status in ("pending", "running"):
                    task.cancel()
            self._tasks.clear()
