"""Scan and read persisted run results from the disk logs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.default_config import DEFAULT_CONFIG


_HISTORY_CACHE = {}
_CACHE_TTL = 30  # seconds


def _results_dir() -> Path:
    """Resolve the configured results directory."""
    path = DEFAULT_CONFIG.get(
        "results_dir",
        os.path.join(os.path.expanduser("~"), ".tradingagents", "logs"),
    )
    return Path(path).expanduser()


def _is_safe_ticker_component(name: str) -> bool:
    """Reject path traversal in ticker-like directory names."""
    if not name:
        return False
    if name in (".", ".."):
        return False
    if "/" in name or "\\" in name:
        return False
    return True


def list_all_runs(
    ticker: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[List[dict], int]:
    """Scan the results directory for completed JSON log files.

    Returns (items, total_count). Each item is a light summary for the
    history list view — not the full state.
    """
    results_dir = _results_dir()
    if not results_dir.exists():
        return [], 0

    all_items = []

    ticker_dirs = sorted(results_dir.iterdir(), reverse=True)
    for ticker_dir in ticker_dirs:
        if not ticker_dir.is_dir():
            continue
        dir_name = ticker_dir.name
        if not _is_safe_ticker_component(dir_name):
            continue
        if ticker and dir_name.upper() != ticker.upper():
            continue

        log_subdir = ticker_dir / "TradingAgentsStrategy_logs"
        if not log_subdir.is_dir():
            continue

        for log_file in sorted(log_subdir.glob("full_states_log_*.json"), reverse=True):
            date_str = log_file.stem.replace("full_states_log_", "")
            all_items.append({
                "run_id": f"{dir_name}__{date_str}",
                "ticker": dir_name,
                "analysis_date": date_str,
                "signal": _extract_signal_from_log(log_file),
                "created_at": datetime.fromtimestamp(
                    log_file.stat().st_mtime
                ).isoformat(),
                "asset_type": "stock",
            })

    total = len(all_items)
    items = all_items[offset : offset + limit]
    return items, total


def _extract_signal_from_log(log_path: Path) -> str:
    """Quickly extract the signal from a JSON log without loading the whole file.

    Falls back to "Unknown" if the file can't be read.
    """
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        from tradingagents.agents.utils.rating import parse_rating

        decision = data.get("final_trade_decision", "")
        return parse_rating(decision)
    except Exception:
        return "Unknown"


def get_run_detail(ticker: str, analysis_date: str) -> Optional[dict]:
    """Load the full JSON state for a specific (ticker, date) run."""
    if not _is_safe_ticker_component(ticker):
        return None

    log_path = (
        _results_dir()
        / ticker
        / "TradingAgentsStrategy_logs"
        / f"full_states_log_{analysis_date}.json"
    )
    if not log_path.exists():
        return None

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_tickers() -> List[str]:
    """Return distinct ticker symbols found in the results directory."""
    results_dir = _results_dir()
    if not results_dir.exists():
        return []

    tickers = []
    for ticker_dir in sorted(results_dir.iterdir()):
        if not ticker_dir.is_dir():
            continue
        dir_name = ticker_dir.name
        if not _is_safe_ticker_component(dir_name):
            continue
        log_subdir = ticker_dir / "TradingAgentsStrategy_logs"
        if log_subdir.is_dir() and any(log_subdir.glob("*.json")):
            tickers.append(dir_name)

    return sorted(tickers)


def get_memory_log_entries() -> List[dict]:
    """Return parsed entries from the memory log."""
    try:
        mem = TradingMemoryLog(DEFAULT_CONFIG)
        entries = mem.load_entries()
        # Merge reflection info with history runs
        return entries
    except Exception:
        return []
