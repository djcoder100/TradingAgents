"""Background thread that executes TradingAgentsGraph.stream() and emits
progress events for SSE subscribers.

This replicates the CLI's streaming logic from cli/main.py's run_analysis(),
pushing agent messages, tool calls, and status transitions as SSE events.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from cli.utils import detect_asset_type
from cli.models import AssetType
from cli.stats_handler import StatsCallbackHandler
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

logger = logging.getLogger("tradingagents.web.analysis_runner")

# ── Agent ordering for the pipeline display ─────────────────────────────────

ANALYST_ORDER = ["market", "social", "news", "fundamentals"]

ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}

ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

FIXED_AGENTS = [
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Trader",
    "Aggressive Analyst",
    "Conservative Analyst",
    "Neutral Analyst",
    "Portfolio Manager",
]


def classify_message_content(message) -> tuple[str, Optional[str]]:
    """Classify a LangChain message and extract its content.

    Mirrors cli/main.py classify_message_type().
    Returns (msg_type, content).
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = None
    raw = getattr(message, "content", None)
    if raw and isinstance(raw, str) and raw.strip():
        content = raw.strip()

    if isinstance(message, HumanMessage):
        if content and content == "Continue":
            return ("control", content)
        return ("user", content)
    if isinstance(message, ToolMessage):
        return ("tool", content)
    if isinstance(message, AIMessage):
        return ("agent", content)
    return ("system", content)


class AnalysisTask:
    """Represents a single analysis run with streaming progress state."""

    def __init__(self, task_id: str, params: dict):
        self.task_id = task_id
        self.params = params
        self.status = "pending"
        self.error: Optional[str] = None

        # Progress state
        self.agent_status: Dict[str, str] = {}
        self.report_sections: Dict[str, str] = {}
        self.agent_times: Dict[str, dict] = {}  # agent_name -> {started, completed}
        self.llm_calls = 0
        self.tool_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.start_time: Optional[float] = None
        self.completed_at: Optional[float] = None

        # Final results
        self.final_state: Optional[Dict[str, Any]] = None
        self.signal: Optional[str] = None
        self.asset_type: str = "stock"
        self.instrument_context: Optional[str] = None

        # Cancellation and threading
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._subscribers: List[asyncio.Queue] = []
        self._processed_message_ids: set = set()
        self._message_count = 0

    def cancel(self) -> None:
        """Signal the task to cancel at the next chunk boundary."""
        logger.info("Task %s: cancellation requested", self.task_id)
        self._cancel_event.set()

    async def subscribe(self) -> asyncio.Queue:
        """Return an asyncio.Queue that will receive SSE events."""
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers.append(q)
        logger.debug("Task %s: new SSE subscriber (total: %d)", self.task_id, len(self._subscribers))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
                logger.debug("Task %s: SSE subscriber removed (remaining: %d)", self.task_id, len(self._subscribers))

    def _emit(self, event: str, data: dict) -> None:
        """Push an event to all SSE subscribers via their queues."""
        payload = json.dumps({"event": event, "data": data})
        with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    loop = asyncio.get_event_loop()
                    loop.call_soon_threadsafe(q.put_nowait, payload)
                except Exception:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    # ── Background thread entry point ───────────────────────────────────────

    def run_in_thread(self) -> None:
        """Main entry point executed in a background thread."""
        self.status = "running"
        self.start_time = time.time()
        logger.info("Task %s: analysis started for %s on %s", self.task_id, self.params.get("ticker"), self.params.get("analysis_date"))

        try:
            self._execute()
            if self._cancel_event.is_set():
                self.status = "cancelled"
                logger.info("Task %s: cancelled by user", self.task_id)
            else:
                self.status = "completed"
                logger.info("Task %s: completed successfully in %.1fs", self.task_id, time.time() - self.start_time)
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            logger.error("Task %s: failed with error: %s", self.task_id, e, exc_info=True)
            self._emit("error", {"message": str(e)})
        finally:
            self.completed_at = time.time()
            elapsed = self.completed_at - (self.start_time or self.completed_at)
            self._emit("complete", {
                "task_id": self.task_id,
                "status": self.status,
                "signal": self.signal,
                "elapsed_seconds": round(elapsed, 2),
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
            })

    def _execute(self) -> None:
        """Replicate the CLI's streaming logic using graph.stream()."""
        ticker = self.params["ticker"]
        asset_type_enum = detect_asset_type(ticker)
        self.asset_type = asset_type_enum.value

        # Build config
        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = self.params["research_depth"]
        config["max_risk_discuss_rounds"] = self.params["research_depth"]
        config["quick_think_llm"] = self.params.get("quick_think_llm", config["quick_think_llm"])
        config["deep_think_llm"] = self.params.get("deep_think_llm", config["deep_think_llm"])
        config["llm_provider"] = self.params.get("llm_provider", config["llm_provider"])
        config["output_language"] = self.params.get("output_language", config["output_language"])

        if self.params.get("backend_url"):
            config["backend_url"] = self.params["backend_url"]
        if self.params.get("google_thinking_level"):
            config["google_thinking_level"] = self.params["google_thinking_level"]
        if self.params.get("openai_reasoning_effort"):
            config["openai_reasoning_effort"] = self.params["openai_reasoning_effort"]
        if self.params.get("anthropic_effort"):
            config["anthropic_effort"] = self.params["anthropic_effort"]
        if self.params.get("temperature") is not None:
            config["temperature"] = self.params["temperature"]

        analysis_date = self.params["analysis_date"]
        analysts = self.params.get("analysts", ["market", "social", "news", "fundamentals"])

        if self.asset_type == "crypto" and "fundamentals" in analysts:
            analysts = [a for a in analysts if a != "fundamentals"]

        logger.info("Task %s: config — provider=%s quick=%s deep=%s depth=%d analysts=%s",
                     self.task_id, config["llm_provider"], config["quick_think_llm"],
                     config["deep_think_llm"], config["max_debate_rounds"], analysts)

        # Build the graph
        stats_handler = StatsCallbackHandler()
        graph = TradingAgentsGraph(
            selected_analysts=analysts,
            config=config,
            debug=True,
            callbacks=[stats_handler],
        )

        self.instrument_context = graph.resolve_instrument_context(ticker, self.asset_type)
        logger.info("Task %s: instrument resolved — %s", self.task_id,
                     self.instrument_context[:120] if self.instrument_context else "none")

        init_state = graph.propagator.create_initial_state(
            ticker, analysis_date,
            asset_type=self.asset_type,
            instrument_context=self.instrument_context,
        )
        args = graph.propagator.get_graph_args()

        # Initialize agent statuses
        self._init_agent_statuses(analysts)
        self._emit("status", {
            "agent_status": self.agent_status,
            "reports_completed": 0,
            "reports_total": len(self.agent_status),
            "llm_calls": 0, "tool_calls": 0,
            "tokens_in": 0, "tokens_out": 0,
            "elapsed_seconds": 0,
        })

        # Emit the "starting" message
        self._emit("message", {
            "type": "system",
            "content": f"Starting analysis of {ticker} on {analysis_date}...",
            "timestamp": datetime.now().isoformat(),
        })

        # Stream chunks
        trace = []
        chunk_count = 0

        for chunk in graph.graph.stream(init_state, **args):
            if self._cancel_event.is_set():
                logger.info("Task %s: cancel event detected after %d chunks", self.task_id, chunk_count)
                return

            trace.append(chunk)
            chunk_count += 1
            self._process_chunk(chunk, stats_handler, analysts)

        logger.info("Task %s: streaming complete — %d chunks processed, %d messages",
                     self.task_id, chunk_count, self._message_count)

        # Merge trace into final state
        final_state = {}
        for chunk in trace:
            final_state.update(chunk)
        self.final_state = final_state

        if final_state.get("final_trade_decision"):
            self.signal = graph.process_signal(final_state["final_trade_decision"])
        logger.info("Task %s: signal = %s", self.task_id, self.signal)

        # Persist to disk — set graph.ticker first since _log_state() reads it
        graph.ticker = ticker
        graph.memory_log.store_decision(
            ticker=ticker, trade_date=analysis_date,
            final_trade_decision=final_state.get("final_trade_decision", ""),
        )
        graph._log_state(analysis_date, final_state)
        logger.info("Task %s: results persisted to disk", self.task_id)

    def _init_agent_statuses(self, analysts: list) -> None:
        """Initialize all agent statuses."""
        for key in analysts:
            name = ANALYST_AGENT_NAMES.get(key, key)
            self.agent_status[name] = "pending"
        for name in FIXED_AGENTS:
            self.agent_status[name] = "pending"

    def _process_chunk(self, chunk: dict, stats_handler, analysts: list) -> None:
        """Extract progress info from a streamed chunk — mirrors the CLI's per-chunk processing."""
        changed = False

        # ── 1. Process messages (agent thinking, tool calls) ────────────────
        for message in chunk.get("messages", []):
            msg_id = getattr(message, "id", None)
            if msg_id is not None:
                if msg_id in self._processed_message_ids:
                    continue
                self._processed_message_ids.add(msg_id)

            msg_type, content = classify_message_content(message)
            if content:
                self._message_count += 1
                # Truncate very long messages for the feed
                display_content = content[:2000] if len(content) > 2000 else content
                self._emit("message", {
                    "type": msg_type,
                    "content": display_content,
                    "truncated": len(content) > 2000,
                    "timestamp": datetime.now().isoformat(),
                })

                # Track tool calls
                tool_calls = getattr(message, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
                        args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                        self._emit("tool_call", {
                            "name": name,
                            "args": str(args)[:500],
                            "timestamp": datetime.now().isoformat(),
                        })

        # ── 2. Update analyst statuses (mirrors CLI's update_analyst_statuses) ──
        self._update_analyst_statuses(chunk, analysts)

        # ── 3. Handle research team transitions ─────────────────────────────
        debate_state = chunk.get("investment_debate_state")
        if debate_state:
            bull_hist = (debate_state.get("bull_history") or "").strip()
            bear_hist = (debate_state.get("bear_history") or "").strip()
            judge = (debate_state.get("judge_decision") or "").strip()

            if bull_hist or bear_hist:
                for name in ["Bull Researcher", "Bear Researcher"]:
                    if self.agent_status.get(name) == "pending":
                        self._agent_start(name)
                        self.agent_status[name] = "running"
                        changed = True

            if bull_hist:
                self.report_sections["investment_plan_bull"] = bull_hist
                self._emit("report", {
                    "section": "research_bull",
                    "agent": "Bull Researcher",
                    "title": "Bull Case",
                    "content": bull_hist,
                    "wall_time": self._agent_wall("Bull Researcher"),
                })
            if bear_hist:
                self.report_sections["investment_plan_bear"] = bear_hist
                self._emit("report", {
                    "section": "research_bear",
                    "agent": "Bear Researcher",
                    "title": "Bear Case",
                    "content": bear_hist,
                    "wall_time": self._agent_wall("Bear Researcher"),
                })
            if judge:
                self.report_sections["investment_plan_judge"] = judge
                for name in ["Bull Researcher", "Bear Researcher"]:
                    self._agent_complete(name)
                    self.agent_status[name] = "completed"
                self._agent_complete("Research Manager")
                self.agent_status["Research Manager"] = "completed"
                changed = True
                self._emit("report", {
                    "section": "research_judge",
                    "agent": "Research Manager",
                    "title": "Research Verdict",
                    "content": judge,
                    "wall_time": self._agent_wall("Research Manager"),
                })

            if bull_hist or bear_hist or judge:
                changed = True

        # ── 4. Handle trader transition ─────────────────────────────────────
        if chunk.get("trader_investment_plan"):
            self.report_sections["trader_investment_plan"] = str(chunk["trader_investment_plan"])
            if self.agent_status.get("Trader") == "pending":
                self.agent_status["Trader"] = "completed"
                changed = True

        # ── 5. Handle risk team transitions ─────────────────────────────────
        risk_state = chunk.get("risk_debate_state")
        if risk_state:
            agg = (risk_state.get("aggressive_history") or "").strip()
            con = (risk_state.get("conservative_history") or "").strip()
            neu = (risk_state.get("neutral_history") or "").strip()
            risk_judge = (risk_state.get("judge_decision") or "").strip()

            for agent, hist in [("Aggressive Analyst", agg), ("Conservative Analyst", con), ("Neutral Analyst", neu)]:
                if hist and self.agent_status.get(agent) == "pending":
                    self.agent_status[agent] = "running"
                    changed = True

            if agg:
                self.report_sections["risk_aggressive"] = agg
            if con:
                self.report_sections["risk_conservative"] = con
            if neu:
                self.report_sections["risk_neutral"] = neu
            if risk_judge:
                self.report_sections["risk_judge"] = risk_judge
                for agent in ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager"]:
                    self.agent_status[agent] = "completed"
                changed = True

            if agg or con or neu or risk_judge:
                changed = True

        # ── 6. Update stats ─────────────────────────────────────────────────
        new_llm = getattr(stats_handler, "llm_call_count", 0)
        new_tool = getattr(stats_handler, "tool_call_count", 0)
        new_ti = getattr(stats_handler, "total_tokens_in", 0)
        new_to = getattr(stats_handler, "total_tokens_out", 0)

        if (new_llm != self.llm_calls or new_tool != self.tool_calls or
                new_ti != self.tokens_in or new_to != self.tokens_out):
            self.llm_calls = new_llm
            self.tool_calls = new_tool
            self.tokens_in = new_ti
            self.tokens_out = new_to
            changed = True

        # ── 7. Emit status if anything changed ──────────────────────────────
        if changed:
            elapsed = time.time() - (self.start_time or time.time())
            completed = sum(1 for s in self.agent_status.values() if s == "completed")
            wall_times = {name: self._agent_wall(name) for name in self.agent_status}
            self._emit("status", {
                "agent_status": self.agent_status,
                "agent_times": wall_times,
                "reports_completed": completed,
                "reports_total": len(self.agent_status),
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "elapsed_seconds": round(elapsed, 2),
            })

    def _agent_start(self, name: str) -> None:
        """Record the wall-clock time when an agent starts running."""
        if name not in self.agent_times:
            self.agent_times[name] = {"started": time.time(), "completed": None}
        elif self.agent_times[name].get("started") is None:
            self.agent_times[name]["started"] = time.time()

    def _agent_complete(self, name: str) -> None:
        """Record the wall-clock time when an agent completes."""
        if name not in self.agent_times:
            self.agent_times[name] = {"started": None, "completed": time.time()}
        else:
            self.agent_times[name]["completed"] = time.time()

    def _agent_wall(self, name: str) -> float:
        """Return the elapsed time for an agent in seconds, or 0 if unknown."""
        t = self.agent_times.get(name, {})
        started = t.get("started")
        if started is None:
            return 0.0
        end = t.get("completed") or time.time()
        return round(max(0, end - started), 2)

    def _update_analyst_statuses(self, chunk: dict, selected_analysts: list) -> None:
        """Mirrors cli/main.py update_analyst_statuses(). Also emits report
        content and wall-time data via SSE when an analyst finishes."""
        found_active = False

        for analyst_key in ANALYST_ORDER:
            if analyst_key not in selected_analysts:
                continue

            agent_name = ANALYST_AGENT_NAMES[analyst_key]
            report_key = ANALYST_REPORT_MAP[analyst_key]

            # Detect new report content
            new_report = chunk.get(report_key)
            if new_report and not self.report_sections.get(report_key):
                content = str(new_report)
                self.report_sections[report_key] = content
                self._agent_complete(agent_name)
                # Emit the full report content so frontend can show it progressively
                self._emit("report", {
                    "section": report_key,
                    "agent": agent_name,
                    "title": agent_name.replace(" Analyst", " Analysis"),
                    "content": content,
                    "wall_time": self._agent_wall(agent_name),
                })
                logger.debug("Task %s: %s report ready (%.1fs)", self.task_id, agent_name, self._agent_wall(agent_name))

            has_report = bool(self.report_sections.get(report_key))

            if has_report:
                self.agent_status[agent_name] = "completed"
            elif not found_active:
                if self.agent_status.get(agent_name) != "running":
                    self._agent_start(agent_name)
                self.agent_status[agent_name] = "running"
                found_active = True
            else:
                self.agent_status[agent_name] = "pending"

        # When all analysts done, start the researchers
        if not found_active and selected_analysts:
            for name in ["Bull Researcher", "Bear Researcher"]:
                if self.agent_status.get(name) == "pending":
                    self._agent_start(name)
                    self.agent_status[name] = "running"
