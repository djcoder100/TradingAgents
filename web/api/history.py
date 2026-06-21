"""API routes for browsing historical analysis runs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from web.services import history_service
from web.models.responses import (
    HistoryResponse,
    HistoryRun,
    MemoryLogResponse,
    MemoryEntry,
    ErrorResponse,
)

router = APIRouter(tags=["history"])


@router.get("/history", response_model=HistoryResponse)
async def list_history(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List completed analysis runs from disk logs."""
    items, total = history_service.list_all_runs(
        ticker=ticker,
        offset=offset,
        limit=limit,
    )

    # Enrich with memory log data (reflections, returns)
    mem_entries = {}
    try:
        for entry in history_service.get_memory_log_entries():
            key = f"{entry.get('ticker', '')}__{entry.get('date', '')}"
            mem_entries[key] = entry
    except Exception:
        pass

    enriched = []
    for item in items:
        mem = mem_entries.get(item["run_id"], {})
        enriched.append(
            HistoryRun(
                run_id=item["run_id"],
                ticker=item["ticker"],
                analysis_date=item["analysis_date"],
                signal=item.get("signal", "Unknown"),
                created_at=item.get("created_at"),
                asset_type=item.get("asset_type", "stock"),
                has_reflection=bool(mem.get("reflection")),
                raw_return=mem.get("raw"),
                alpha_return=mem.get("alpha"),
            )
        )

    return HistoryResponse(
        items=enriched,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/history/tickers")
async def list_tickers():
    """Return distinct ticker symbols found in archived runs."""
    tickers = history_service.list_tickers()
    return {"tickers": tickers}


@router.get("/history/run/{run_id}")
async def get_run_detail(run_id: str):
    """Get the full JSON log for a specific run.

    run_id format: <TICKER>__<YYYY-MM-DD>
    """
    parts = run_id.split("__", 1)
    if len(parts) != 2:
        return ErrorResponse(detail=f"Invalid run_id format: {run_id}")

    ticker, date_str = parts
    result = history_service.get_run_detail(ticker, date_str)
    if result is None:
        return ErrorResponse(detail=f"Run not found: {run_id}")

    return result


@router.get("/history/memory", response_model=MemoryLogResponse)
async def get_memory_log():
    """Return parsed memory log entries with reflections."""
    entries = history_service.get_memory_log_entries()

    mem_entries = []
    for e in entries:
        mem_entries.append(
            MemoryEntry(
                date=e.get("date", ""),
                ticker=e.get("ticker", ""),
                rating=e.get("rating", ""),
                pending=e.get("pending", False),
                raw=e.get("raw"),
                alpha=e.get("alpha"),
                holding=e.get("holding"),
                decision=e.get("decision"),
                reflection=e.get("reflection"),
            )
        )

    return MemoryLogResponse(entries=mem_entries)
