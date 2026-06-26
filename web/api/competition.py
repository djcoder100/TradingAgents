# web/api/competition.py
"""API routes for the competition engine dashboard.

Reads live state from either:
1. In-process CompetitionStateBus (when engine runs with --web)
2. External state service (when engine and web are separate processes)

Supports both monolithic (engine+web together) and distributed (separate
processes) deployments.
"""

from __future__ import annotations

import os
import logging
import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["competition"])


def _get_bus(request: Request):
    """Return the CompetitionStateBus from the app, or None if not running."""
    return getattr(request.app.state, "competition_bus", None)


def _get_state_service_state():
    """Fetch state from external state service (for separate processes)."""
    state_service_url = os.environ.get("COMPETITION_STATE_SERVICE_URL", "http://localhost:9000")
    try:
        resp = requests.get(f"{state_service_url}/api/competition/state", timeout=2)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"State service unavailable: {e}")
    return None


def _get_state(request: Request):
    """Get state from bus or state service, whichever is available."""
    bus = _get_bus(request)
    if bus is not None:
        return bus.snapshot(), None

    # Try state service (separate processes mode)
    state = _get_state_service_state()
    if state is not None:
        return state, None

    return None, JSONResponse(
        {"error": "Competition engine not running. Start with: uv run competition --mock --dry-run"},
        status_code=503,
    )


@router.get("/competition/state")
async def get_competition_state(request: Request):
    """Full snapshot: signals, positions, trades, account, metrics."""
    state, error = _get_state(request)
    if error is not None:
        return error
    return state


@router.get("/competition/signals")
async def get_signals(request: Request):
    """Active signals with their analysis."""
    snap, error = _get_state(request)
    if error is not None:
        return error
    return {"signals": snap["signals"], "last_updated": snap["last_updated"]}


@router.get("/competition/positions")
async def get_positions(request: Request):
    """Open positions with unrealized P&L."""
    snap, error = _get_state(request)
    if error is not None:
        return error
    return {"positions": snap["positions"], "last_updated": snap["last_updated"]}


@router.get("/competition/trades")
async def get_trades(request: Request, limit: int = 50):
    """Recent trade history."""
    snap, error = _get_state(request)
    if error is not None:
        return error
    trades = snap["trades"][-limit:]
    return {"trades": list(reversed(trades)), "last_updated": snap["last_updated"]}


@router.get("/competition/analysis/{ticker}")
async def get_analysis_detail(ticker: str, request: Request):
    """Full pipeline analysis for a ticker (analyst reports, debate, decision)."""
    snap, error = _get_state(request)
    if error is not None:
        return error

    # Try direct lookup by analysis_id first, then by ticker
    bus = _get_bus(request)
    if bus is not None:
        data = bus.get_full_analysis(ticker)
    else:
        # State service mode: look up in full_analysis dict
        data = snap.get("full_analysis", {}).get(ticker)
        if data is None:
            # Try to find by ticker in latest_analysis_id
            latest_id = snap.get("latest_analysis_id", {}).get(ticker.upper())
            if latest_id:
                data = snap.get("full_analysis", {}).get(latest_id)

    if data is None:
        return JSONResponse(
            {"error": f"No analysis available for {ticker.upper()} yet — run the LLM pipeline first."},
            status_code=404,
        )
    return data


@router.get("/competition/metrics")
async def get_metrics(request: Request):
    """Live scoring metrics (Return, MaxDD, Sharpe)."""
    snap, error = _get_state(request)
    if error is not None:
        return error
    return {
        "metrics": snap["metrics"],
        "account": snap["account"],
        "violations": snap["violations"],
        "uptime": snap["uptime"],
        "last_updated": snap["last_updated"],
    }


@router.get("/competition/broker")
async def get_broker_info(request: Request):
    """Get information about the current broker connection."""
    # Detect broker from environment or state
    import os

    broker_env = os.environ.get("COMPETITION_BROKER", "mock")

    # Try to get broker type from state (if set by engine)
    snap, _ = _get_state(request)
    broker_type = snap.get("broker_type", broker_env) if snap else broker_env

    # Map broker type to display name and features
    broker_info = {
        "mock": {
            "name": "Mock Broker (Simulated)",
            "type": "mock",
            "mode": "simulated",
            "features": ["testing", "development"],
            "manual_trading": False,
            "api_available": False,
        },
        "alpaca": {
            "name": "Alpaca (REST API)",
            "type": "alpaca",
            "mode": "paper" if os.environ.get("ALPACA_IS_PAPER", "true").lower() in ("true", "1") else "live",
            "features": ["stocks", "crypto", "macOS"],
            "manual_trading": False,
            "api_available": True,
        },
        "oanda": {
            "name": "OANDA (REST API)",
            "type": "oanda",
            "mode": "practice" if os.environ.get("OANDA_ENVIRONMENT", "practice") == "practice" else "live",
            "features": ["forex", "metals", "50:1 leverage", "macOS"],
            "manual_trading": False,
            "api_available": True,
        },
        "mt5": {
            "name": "MetaTrader5 (Desktop Client)",
            "type": "mt5",
            "mode": "demo" if os.environ.get("MT5_ACCOUNT_TYPE", "demo") == "demo" else "live",
            "features": ["forex", "stocks", "options", "manual entry"],
            "manual_trading": True,
            "api_available": True,
        },
    }

    info = broker_info.get(broker_type, broker_info["mock"])
    info["broker_type"] = broker_type

    return info


@router.get("/competition/settings")
def get_settings():
    """Return current engine configuration for display in frontend settings panel."""
    return {
        "llm_provider": os.environ.get("TRADINGAGENTS_LLM_PROVIDER", "unknown"),
        "llm_backend_url": os.environ.get("TRADINGAGENTS_LLM_BACKEND_URL", "default"),
        "quick_think_model": os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM", "unknown"),
        "deep_think_model": os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM", "unknown"),
        "instruments": os.environ.get("COMPETITION_INSTRUMENTS", "XAUUSD,EURUSD,GBPUSD"),
        "day_trading_mode": os.environ.get("COMPETITION_DAY_TRADING", "false").lower() == "true",
        "close_at_eod": os.environ.get("COMPETITION_CLOSE_AT_EOD", "true").lower() == "true",
        "dry_run": os.environ.get("COMPETITION_DRY_RUN", "false").lower() == "true",
        "state_service_url": os.environ.get("COMPETITION_STATE_SERVICE_URL", "http://localhost:9000"),
        "web_port": os.environ.get("TRADINGAGENTS_WEB_PORT", "8000"),
        "frontend_port": os.environ.get("VITE_PORT", "5173"),
    }
