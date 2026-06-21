"""
Standalone state service for inter-process communication.

The engine and web frontend both connect to this service via REST API.
This allows them to run as separate processes (or on different machines)
while sharing live state.

Usage:
    uvicorn competition.state_service:app --host 0.0.0.0 --port 9000
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import json
import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# In-memory state (persisted to disk on updates)
_STATE: Dict[str, Any] = {
    "signals": {},
    "positions": [],
    "trades": [],
    "account": None,
    "metrics": None,
    "analysis_progress": {},
    "full_analysis": {},
    "active_analysis": {},
    "latest_analysis_id": {},
    "last_updated": 0.0,
    "uptime": "00:00:00",
    "round_trip_count": 0,
    "violations": [],
}

_LOCK = Lock()
_STATE_FILE = Path.home() / ".tradingagents" / "shared_state.json"

app = FastAPI(title="Competition State Service")


def _load_state() -> None:
    """Load state from disk on startup."""
    global _STATE
    if _STATE_FILE.exists():
        try:
            with open(_STATE_FILE) as f:
                _STATE = json.load(f)
            logger.info(f"Loaded state from {_STATE_FILE}")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")


def _save_state() -> None:
    """Persist state to disk (called after updates)."""
    try:
        # Always update last_updated when state changes
        _STATE["last_updated"] = time.time()
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE_FILE, "w") as f:
            json.dump(_STATE, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


@app.on_event("startup")
async def startup():
    """Load persisted state on startup."""
    _load_state()


@app.get("/api/competition/state")
async def get_state():
    """Get the full current state (read-only)."""
    with _LOCK:
        # Normalize signals from dict to array for frontend compatibility
        state = dict(_STATE)
        if isinstance(state.get("signals"), dict):
            state["signals"] = [
                {**v, "ticker": k}
                for k, v in state["signals"].items()
            ]

        # Calculate elapsed_s for analysis progress (dynamic, like the bus does)
        if isinstance(state.get("analysis_progress"), dict):
            state["analysis_progress"] = {
                t: {**p, "elapsed_s": time.time() - p.get("started_at", time.time())}
                for t, p in state["analysis_progress"].items()
            }

        return JSONResponse(state)


@app.post("/api/competition/state/update")
async def update_state(key: str, request: Request):
    """Update a single state key and persist."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    with _LOCK:
        _STATE[key] = body
        _save_state()
    return {"status": "ok", "key": key}


@app.post("/api/competition/state/merge")
async def merge_state(updates: Dict[str, Any]):
    """Merge updates into state (for complex nested updates)."""
    with _LOCK:
        for key, value in updates.items():
            if isinstance(value, dict) and key in _STATE and isinstance(_STATE[key], dict):
                _STATE[key].update(value)
            else:
                _STATE[key] = value
        _save_state()
    return {"status": "ok", "keys": list(updates.keys())}


@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    _load_state()
    uvicorn.run(app, host="0.0.0.0", port=9000)
