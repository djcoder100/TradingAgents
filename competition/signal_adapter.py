# competition/signal_adapter.py
"""Bridge between TradingAgents multi-agent pipeline and competition TradeSignals.

Runs a lightweight TradingAgents analysis (market + fundamentals only, single
debate rounds) and converts the PortfolioDecision into a actionable TradeSignal
with directional bias, price targets, and position sizing.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Optional

from competition.models import TradeSignal, OrderAction, AccountState
from competition.config import (
    DEFAULT_POSITION_PCT,
    MAX_POSITION_PCT,
    MIN_ORDER_NOTIONAL,
    SIGNAL_STALE_S,
    TA_ANALYSTS,
    TA_MAX_DEBATE_ROUNDS,
    TA_MAX_RISK_ROUNDS,
)

logger = logging.getLogger(__name__)

# Human-readable labels for TradingAgents LangGraph node names.
# Tool nodes and message-clear nodes are filtered out by the graph callback.
_NODE_LABELS: dict[str, str] = {
    "Market Analyst": "Market Analyst — price action & technicals",
    "Sentiment Analyst": "Sentiment Analyst — social media sentiment",
    "News Analyst": "News Analyst — news & insider activity",
    "Fundamentals Analyst": "Fundamentals Analyst — financial statements",
    "Bull Researcher": "Bull Researcher — building the bull case",
    "Bear Researcher": "Bear Researcher — building the bear case",
    "Research Manager": "Research Manager — synthesizing thesis",
    "Trader": "Trader — sizing the trade",
    "Aggressive Analyst": "Risk: Aggressive — stress-testing upside",
    "Conservative Analyst": "Risk: Conservative — stress-testing downside",
    "Neutral Analyst": "Risk: Neutral — balanced risk view",
    "Portfolio Manager": "Portfolio Manager — final decision",
}
def _compute_total_stages(analysts: list[str], max_debate: int, max_risk: int) -> int:
    """Compute expected pipeline node firings.

    Formula from conditional_logic.py:
      debate exits when count >= 2 * max_debate_rounds  → 2 * max_debate Bull+Bear nodes
      risk exits when count  >= 3 * max_risk_rounds     → 3 * max_risk  Agg+Con+Neu nodes
    """
    return len(analysts) + (2 * max_debate) + 1 + 1 + (3 * max_risk) + 1

# Confidence mapping: PortfolioRating → 0.0–1.0
_RATING_CONFIDENCE = {
    "buy": 0.90,
    "overweight": 0.70,
    "hold": 0.50,
    "underweight": 0.30,
    "sell": 0.10,
}

# Regex for position sizing hints like "5% of portfolio", "6% allocation"
_SIZE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%?\s*(?:of\s+)?(?:portfolio|allocation|equity|capital|position)",
    re.IGNORECASE,
)


class SignalAdapter:
    """Converts TradingAgents analysis output into competition-ready TradeSignals."""

    def __init__(self, config: Optional[dict] = None):
        # Accept a full TradingAgents config dict (provider, models, backend_url,
        # temperature, etc.) so the caller can pass through DEFAULT_CONFIG with
        # env-var overrides. Falls back to sane defaults if nothing is supplied.
        if config is None:
            from tradingagents.default_config import DEFAULT_CONFIG
            config = DEFAULT_CONFIG.copy()
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_analysis_for_instrument(
        self, ticker: str, trade_date: str, state_bus=None
    ) -> Optional[dict]:
        """Run a lightweight TradingAgents analysis for a single instrument.

        Returns a dict with keys: *rating*, *action*, *price_target*,
        *stop_loss*, *position_pct*, *summary*, *thesis*, or None on failure.

        Called from a daemon thread — Ctrl+C kills the process including any
        in-progress LLM call, so no timeout guard is needed.
        """
        try:
            from tradingagents.graph.trading_graph import TradingAgentsGraph
            from tradingagents.agents.utils.rating import parse_rating
            from tradingagents.agents.utils.agent_utils import resolve_instrument_identity
        except ImportError as e:
            logger.error("Cannot import TradingAgents: %s", e)
            return None

        # Start from the configured defaults (provider, models, keys, backend_url,
        # etc.) and layer competition-specific overrides on top.
        cfg = self.config.copy()
        cfg["max_debate_rounds"] = TA_MAX_DEBATE_ROUNDS
        cfg["max_risk_discuss_rounds"] = TA_MAX_RISK_ROUNDS

        logger.info(
            "Starting TA analysis for %s | provider=%s quick=%s deep=%s",
            ticker,
            cfg.get("llm_provider"),
            cfg.get("quick_think_llm"),
            cfg.get("deep_think_llm"),
        )

        try:
            graph = TradingAgentsGraph(
                selected_analysts=TA_ANALYSTS,
                config=cfg,
                debug=False,
            )
            identity = resolve_instrument_identity(ticker)
            name = (identity or {}).get("company_name", ticker)
            logger.info("TA: %s resolved → %s, running pipeline...", ticker, name)

            analysis_id = f"{ticker}-{uuid.uuid4().hex[:8]}"
            started_at = time.time()
            step_counter = [0]
            last_node = [None]  # deduplicate consecutive firings of the same node (tool-calling loop)
            total_stages = _compute_total_stages(TA_ANALYSTS, TA_MAX_DEBATE_ROUNDS, TA_MAX_RISK_ROUNDS)
            node_times: dict[str, list[float]] = {}  # node_name → [start, end] times for timing

            def _on_node(node_name: str) -> None:
                label = _NODE_LABELS.get(node_name)
                if label is None:
                    return
                # Each analyst fires N times during its tool-calling loop. Only count
                # the first firing (node transition); subsequent same-node firings just
                # update the dashboard label without advancing the counter.
                if node_name != last_node[0]:
                    # End previous node timing
                    if last_node[0] is not None and last_node[0] in node_times:
                        node_times[last_node[0]].append(time.time())
                    # Start new node timing
                    if node_name not in node_times:
                        node_times[node_name] = [time.time()]

                    step_counter[0] = min(step_counter[0] + 1, total_stages)
                    last_node[0] = node_name

                    elapsed = time.time() - started_at
                    logger.info(
                        "TA [%s] %d/%d — %s [+%.1fs total]",
                        ticker, step_counter[0], total_stages, label, elapsed,
                    )
                    if state_bus is not None:
                        state_bus.set_analysis_progress(
                            ticker, label, step_counter[0], total_stages, started_at
                        )

            if state_bus is not None:
                state_bus.set_analysis_progress(ticker, "Initializing pipeline…", 0, total_stages, started_at)

            pipeline_start = time.time()
            final_state, _signal_ta = graph.propagate(ticker, trade_date, progress_callback=_on_node)
            pipeline_elapsed = time.time() - pipeline_start

            # End final node timing
            if last_node[0] is not None and last_node[0] in node_times:
                node_times[last_node[0]].append(time.time())

            logger.info("TA [%s] pipeline completed in %.1f seconds", ticker, pipeline_elapsed)

            decision_text = final_state.get("final_trade_decision", "")
            if not decision_text:
                logger.warning("No final_trade_decision for %s", ticker)
                return None

            rating = parse_rating(decision_text)
            result = self._parse_decision(decision_text, rating, identity)
            logger.info(
                "TA signal for %s (%s): rating=%s action=%s confidence=%.2f [%d nodes, %.1f sec total]",
                ticker, name, rating, result.get("action"), result.get("confidence", 0),
                len(node_times), pipeline_elapsed,
            )
            if state_bus is not None:
                state_bus.clear_analysis_progress(ticker)
                state_bus.set_full_analysis(
                    analysis_id,
                    self._build_full_analysis(analysis_id, ticker, trade_date, final_state, result, identity, node_times, pipeline_elapsed),
                )
            result["analysis_id"] = analysis_id
            return result

        except Exception as exc:
            logger.error("TradingAgents analysis failed for %s: %s", ticker, exc)
            if state_bus is not None:
                state_bus.clear_analysis_progress(ticker)
            return None

    def portfolio_decision_to_signal(
        self,
        decision: dict,
        account: AccountState,
        ticker: str,
    ) -> Optional[TradeSignal]:
        """Convert a parsed decision dict into a sized TradeSignal."""
        action_str = decision.get("action", "HOLD")
        try:
            action = OrderAction(action_str.upper())
        except ValueError:
            action = OrderAction.HOLD

        if action == OrderAction.HOLD:
            return None  # no trade to propose

        # Position sizing
        pct = decision.get("position_pct") or DEFAULT_POSITION_PCT
        pct = min(float(pct), MAX_POSITION_PCT)
        notional = account.equity * pct
        if notional < MIN_ORDER_NOTIONAL:
            logger.debug("Skipping %s — notional $%.0f below minimum", ticker, notional)
            return None

        signal = TradeSignal(
            action=action,
            ticker=ticker,
            order_size_notional=round(notional, 2),
            entry_price_target=decision.get("price_target"),
            stop_loss=decision.get("stop_loss"),
            take_profit=decision.get("price_target"),  # reuse price target as TP
            confidence=float(decision.get("confidence", 0.5)),
            created_at=time.time(),
            expires_at=time.time() + SIGNAL_STALE_S,
        )
        return signal

    @staticmethod
    def select_instruments_to_analyze(
        available_instruments: list[str],
        active_signals: dict[str, TradeSignal],
        max_count: int = 5,
    ) -> list[str]:
        """Pick which instruments to run full TradingAgents analysis on.

        Priority: (1) instruments with no signal or expired signal,
        (2) we don't exceed *max_count* running analyses per cycle.
        """
        candidates = []
        for ticker in available_instruments:
            sig = active_signals.get(ticker)
            if sig is None or sig.is_expired():
                candidates.append(ticker)

        # If we have too many candidates, just pick the first N.
        # In production, you'd sort by recent volatility or opportunity.
        return candidates[:max_count]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_full_analysis(
        analysis_id: str,
        ticker: str,
        trade_date: str,
        final_state: dict,
        parsed: dict,
        identity: Optional[dict] = None,
        node_times: Optional[dict[str, list[float]]] = None,
        elapsed_seconds: float = 0.0,
    ) -> dict:
        """Package the complete pipeline state into AnalysisResultResponse shape."""
        inv = final_state.get("investment_debate_state") or {}
        risk = final_state.get("risk_debate_state") or {}
        rating = parsed.get("rating", "hold").capitalize()
        name = (identity or {}).get("company_name", ticker) if identity else ticker

        # Compute per-node wall-clock times
        analyst_times = {}
        if node_times:
            for node_name, times in node_times.items():
                if len(times) >= 2:
                    node_label = _NODE_LABELS.get(node_name, node_name)
                    analyst_times[node_label] = round(times[-1] - times[0], 2)

        return {
            "task_id": analysis_id,
            "ticker": ticker,
            "instrument_name": name,
            "analysis_date": trade_date,
            "signal": rating,
            "analysts_used": list(_NODE_LABELS.keys()),
            "final_state": {
                "market_report": final_state.get("market_report"),
                "sentiment_report": final_state.get("sentiment_report"),
                "news_report": final_state.get("news_report"),
                "fundamentals_report": final_state.get("fundamentals_report"),
                "investment_plan": final_state.get("investment_plan"),
                "trader_investment_plan": final_state.get("trader_investment_decision"),
                "final_trade_decision": final_state.get("final_trade_decision"),
                "investment_debate_state": {
                    "bull_history": inv.get("bull_history"),
                    "bear_history": inv.get("bear_history"),
                    "judge_decision": inv.get("judge_decision"),
                },
                "risk_debate_state": {
                    "aggressive_history": risk.get("aggressive_history"),
                    "conservative_history": risk.get("conservative_history"),
                    "neutral_history": risk.get("neutral_history"),
                    "judge_decision": risk.get("judge_decision"),
                },
            },
            "stats": {
                "llm_calls": 0,
                "tool_calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "analyst_wall_times": analyst_times,
            },
            "asset_type": "stock",
            "instrument_context": None,
        }

    @staticmethod
    def _parse_decision(
        text: str, rating: str, identity: Optional[dict] = None
    ) -> dict:
        """Extract structured fields from the Portfolio Manager's rendered markdown."""
        action_map = {
            "buy": OrderAction.BUY.value,
            "overweight": OrderAction.BUY.value,
            "hold": OrderAction.HOLD.value,
            "underweight": OrderAction.SELL.value,
            "sell": OrderAction.SELL.value,
        }
        action = action_map.get(rating.lower(), OrderAction.HOLD.value)
        confidence = _RATING_CONFIDENCE.get(rating.lower(), 0.5)

        # Extract price target from the markdown (look for $XXX.XX patterns near "target")
        price_target = None
        target_match = re.search(
            r"(?:price\s*target|target\s*price|PT)[:\s]*\$?(\d+(?:\.\d+)?)",
            text, re.IGNORECASE,
        )
        if target_match:
            try:
                price_target = float(target_match.group(1))
            except ValueError:
                pass

        # Extract stop loss
        stop_loss = None
        stop_match = re.search(
            r"(?:stop[-\s]?loss|SL)[:\s]*\$?(\d+(?:\.\d+)?)",
            text, re.IGNORECASE,
        )
        if stop_match:
            try:
                stop_loss = float(stop_match.group(1))
            except ValueError:
                pass

        # Extract position sizing percentage
        position_pct = None
        size_match = _SIZE_RE.search(text)
        if size_match:
            try:
                pct = float(size_match.group(1))
                # If the number looks like a percentage (>1 likely means %)
                if pct > 1:
                    position_pct = pct / 100.0
                else:
                    position_pct = pct
            except ValueError:
                pass

        # Extract executive summary
        summary = ""
        summary_match = re.search(
            r"\*\*Executive Summary\*\*[:\s]*(.*?)(?=\*\*Investment Thesis\*\*|\Z)",
            text, re.DOTALL | re.IGNORECASE,
        )
        if summary_match:
            summary = summary_match.group(1).strip()

        # Extract investment thesis
        thesis = ""
        thesis_match = re.search(
            r"\*\*Investment Thesis\*\*[:\s]*(.*?)(?=\Z)",
            text, re.DOTALL | re.IGNORECASE,
        )
        if thesis_match:
            thesis = thesis_match.group(1).strip()

        return {
            "rating": rating,
            "action": action,
            "confidence": confidence,
            "price_target": price_target,
            "stop_loss": stop_loss,
            "position_pct": position_pct,
            "summary": summary,
            "thesis": thesis,
        }
