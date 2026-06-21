"""API routes for starting, monitoring, and retrieving analysis runs."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from web.models.requests import AnalysisStartRequest
from web.models.responses import (
    AnalysisStartResponse,
    AnalysisResultResponse,
    AnalysisResultFinalState,
    AnalysisStats,
    DebateState,
    RiskDebateState,
    TaskStatusResponse,
    TaskProgress,
    ErrorResponse,
)
from web.services.task_manager import TaskManager

logger = logging.getLogger("tradingagents.web.api.analysis")

router = APIRouter(tags=["analysis"])


def _get_task_manager(request: Request) -> TaskManager:
    """Dependency: get the TaskManager from app state."""
    return request.app.state.task_manager


@router.post("/analysis/start", response_model=AnalysisStartResponse, status_code=202)
async def start_analysis(body: AnalysisStartRequest, request: Request):
    """Start a new background analysis task."""
    tm = _get_task_manager(request)

    # Validate the date is not in the future
    try:
        analysis_date = datetime.strptime(body.analysis_date, "%Y-%m-%d")
        if analysis_date > datetime.now():
            raise HTTPException(
                status_code=422,
                detail="Analysis date cannot be in the future",
            )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid date format — use YYYY-MM-DD",
        )

    # Create and launch the task
    task = tm.create_task(body.model_dump())
    logger.info("Analysis started: task=%s ticker=%s date=%s provider=%s depth=%d analysts=%s",
                 task.task_id, body.ticker, body.analysis_date,
                 body.llm_provider, body.research_depth, body.analysts)

    return AnalysisStartResponse(
        task_id=task.task_id,
        status=task.status,
        ticker=body.ticker,
        analysis_date=body.analysis_date,
        created_at=datetime.now().isoformat(),
    )


@router.get("/analysis/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, request: Request):
    """Poll for task progress."""
    tm = _get_task_manager(request)
    task = tm.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    progress = TaskProgress(
        agent_status=task.agent_status,
        reports_completed=sum(
            1 for s in task.agent_status.values() if s == "completed"
        ),
        reports_total=len(task.agent_status),
        llm_calls=task.llm_calls,
        tool_calls=task.tool_calls,
        tokens_in=task.tokens_in,
        tokens_out=task.tokens_out,
        elapsed_seconds=(
            (task.completed_at or __import__("time").time()) - (task.start_time or 0)
            if task.start_time
            else 0
        ),
    )

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        progress=progress,
        error=task.error,
    )


@router.get("/analysis/{task_id}/stream")
async def stream_task_events(task_id: str, request: Request):
    """Server-Sent Events endpoint for live progress streaming."""
    tm = _get_task_manager(request)
    task = tm.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    queue = await task.subscribe()

    async def event_generator():
        try:
            # Send current state on connect
            if task.status in ("completed", "failed", "cancelled"):
                yield {
                    "event": task.status,
                    "data": json.dumps({
                        "task_id": task.task_id,
                        "signal": task.signal,
                        "status": task.status,
                        "error": task.error,
                    }),
                }
                return

            # Send initial status snapshot
            status_data = json.dumps({
                "agent_status": task.agent_status,
                "reports_completed": sum(
                    1 for s in task.agent_status.values() if s == "completed"
                ),
                "reports_total": len(task.agent_status),
                "llm_calls": task.llm_calls,
                "tool_calls": task.tool_calls,
                "tokens_in": task.tokens_in,
                "tokens_out": task.tokens_out,
                "elapsed_seconds": 0.0,
            })
            yield {"event": "status", "data": status_data}

            # Stream ongoing events
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30)
                    data = json.loads(payload)
                    event_type = data.get("event", "message")
                    event_data = json.dumps(data.get("data", {}))
                    yield {"event": event_type, "data": event_data}

                    if event_type in ("complete", "error"):
                        return
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "keepalive", "data": "{}"}
        except asyncio.CancelledError:
            pass
        finally:
            task.unsubscribe(queue)

    return EventSourceResponse(event_generator())


@router.get("/analysis/{task_id}/result", response_model=AnalysisResultResponse)
async def get_task_result(task_id: str, request: Request):
    """Get the full completed result. Blocks until done (or returns 404)."""
    tm = _get_task_manager(request)
    task = tm.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {task.error}",
        )

    if task.status in ("pending", "running"):
        # Wait for completion (poll with timeout)
        for _ in range(600):  # max 10 minutes
            await asyncio.sleep(1)
            if task.status in ("completed", "failed", "cancelled"):
                break

    if task.status != "completed":
        raise HTTPException(
            status_code=500,
            detail=f"Analysis did not complete: {task.status}",
        )

    if task.final_state is None:
        raise HTTPException(status_code=500, detail="No result data available")

    fs = task.final_state

    # Build the debate state objects
    invest_state = fs.get("investment_debate_state", {}) or {}
    risk_state = fs.get("risk_debate_state", {}) or {}

    final_state = AnalysisResultFinalState(
        market_report=fs.get("market_report"),
        sentiment_report=fs.get("sentiment_report"),
        news_report=fs.get("news_report"),
        fundamentals_report=fs.get("fundamentals_report"),
        investment_plan=fs.get("investment_plan"),
        trader_investment_plan=fs.get("trader_investment_plan"),
        final_trade_decision=fs.get("final_trade_decision"),
        investment_debate_state=DebateState(
            bull_history=invest_state.get("bull_history"),
            bear_history=invest_state.get("bear_history"),
            judge_decision=invest_state.get("judge_decision"),
        ),
        risk_debate_state=RiskDebateState(
            aggressive_history=risk_state.get("aggressive_history"),
            conservative_history=risk_state.get("conservative_history"),
            neutral_history=risk_state.get("neutral_history"),
            judge_decision=risk_state.get("judge_decision"),
        ),
    )

    stats = AnalysisStats(
        llm_calls=task.llm_calls,
        tool_calls=task.tool_calls,
        tokens_in=task.tokens_in,
        tokens_out=task.tokens_out,
        elapsed_seconds=round(
            (task.completed_at or 0) - (task.start_time or 0), 2
        ),
    )

    return AnalysisResultResponse(
        task_id=task.task_id,
        ticker=task.params.get("ticker", ""),
        analysis_date=task.params.get("analysis_date", ""),
        signal=task.signal or "Hold",
        final_state=final_state,
        stats=stats,
        asset_type=task.asset_type,
        instrument_context=task.instrument_context,
    )


@router.delete("/analysis/{task_id}")
async def cancel_analysis(task_id: str, request: Request):
    """Cancel a running analysis task."""
    tm = _get_task_manager(request)
    logger.info("Cancel requested for task %s", task_id)
    if not tm.cancel_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    logger.info("Task %s cancelled", task_id)
    return {"status": "cancelled", "task_id": task_id}
