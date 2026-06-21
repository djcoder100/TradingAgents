#!/usr/bin/env python3
# competition/main.py
"""Entry point for the competition trading bot.

Loads TradingAgents' default configuration (which reads .env and
TRADINGAGENTS_* env vars at import time), so all providers, API keys,
and model selections work exactly as they do in the main CLI.

Usage:
    uv run competition --mock --dry-run --no-llm
    uv run competition --mock --dry-run
    uv run competition --mock --instruments XAUUSD,EURUSD,BTCUSD
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading

# Importing DEFAULT_CONFIG triggers .env loading and TRADINGAGENTS_* env-var
# overrides — same behaviour as the main TradingAgents CLI.
from tradingagents.default_config import DEFAULT_CONFIG

from competition.config import DEFAULT_INSTRUMENTS
from competition.risk_firewall import ExecutionEngine
from competition.api_client import MockBrokerClient
from competition.signal_adapter import SignalAdapter
from competition.engine import CompetitionEngine


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for competition audit trail."""
    fmt = "%(asctime)s [%(levelname)-7s] %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt=datefmt,
        stream=sys.stdout,
    )
    # Quiet down noisy third-party loggers
    for noisy in ("yfinance", "urllib3", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Ensure TradingAgents' own loggers are at INFO so we see pipeline progress
    for ta_logger in ("tradingagents", "tradingagents.graph", "tradingagents.agents"):
        logging.getLogger(ta_logger).setLevel(logging.INFO)


def parse_args() -> argparse.Namespace:
    # Defaults from TradingAgents config (which includes .env + env-var overrides)
    default_provider = DEFAULT_CONFIG.get("llm_provider", "openai")
    default_quick = DEFAULT_CONFIG.get("quick_think_llm", "gpt-5.4-mini")
    default_deep = DEFAULT_CONFIG.get("deep_think_llm", "gpt-5.5")
    default_backend = DEFAULT_CONFIG.get("backend_url", None)

    p = argparse.ArgumentParser(
        description="Competition Trading Bot — TradingAgents + Risk Firewall",
    )
    p.add_argument(
        "--mock", action="store_true", default=True,
        help="Use the mock broker client for local testing (default).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Run the full loop but do not dispatch orders.",
    )
    p.add_argument(
        "--instruments", type=str, default=None,
        help="Comma-separated instrument list override (e.g. XAUUSD,EURUSD).",
    )
    p.add_argument(
        "--max-positions", type=int, default=8,
        help="Maximum concurrent open positions (default: 8).",
    )
    p.add_argument(
        "--log-level", type=str, default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity (default: INFO).",
    )
    p.add_argument(
        "--llm-provider", type=str, default=default_provider,
        help=f"LLM provider (default: {default_provider}, from "
             f"$TRADINGAGENTS_LLM_PROVIDER or config).",
    )
    p.add_argument(
        "--quick-model", type=str, default=default_quick,
        help=f"Model for analysts/trader (default: {default_quick}, from "
             f"$TRADINGAGENTS_QUICK_THINK_LLM or config).",
    )
    p.add_argument(
        "--deep-model", type=str, default=default_deep,
        help=f"Model for research/portfolio managers (default: {default_deep}, "
             f"from $TRADINGAGENTS_DEEP_THINK_LLM or config).",
    )
    p.add_argument(
        "--backend-url", type=str, default=default_backend,
        help="Override the API endpoint (default: provider default, or "
             "$TRADINGAGENTS_LLM_BACKEND_URL).",
    )
    p.add_argument(
        "--no-llm", action="store_true",
        help="Skip TradingAgents LLM analysis. Use only indicator-based signals "
             "(RSI/MACD/Bollinger) for entry/exit timing. No API key needed.",
    )
    p.add_argument(
        "--web", action="store_true",
        help="Start a FastAPI server alongside the engine so the web dashboard "
             "can display live signals, positions, trades, and metrics.",
    )
    p.add_argument(
        "--web-only", action="store_true",
        help="Start ONLY the web dashboard (engine runs separately). "
             "Reads trade history from disk. Use this to view historical trades "
             "while the engine is stopped or running in another process.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger("competition")

    # Handle --web-only mode (dashboard without engine)
    if args.web_only:
        import uvicorn
        from web.main import app
        logger.info("Starting web-only mode (engine runs separately)")
        logger.info("Reading state from: %s", os.environ.get("COMPETITION_STATE_SERVICE_URL", "http://localhost:9000"))
        # Don't set app.state.competition_bus — let the web API read from state service instead
        logger.info("Web dashboard: http://0.0.0.0:8000")
        logger.info("Frontend: cd frontend && npm run dev   (then open http://localhost:5173/competition)")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
        return

    instruments = DEFAULT_INSTRUMENTS
    if args.instruments:
        instruments = [s.strip() for s in args.instruments.split(",") if s.strip()]

    # Build the TradingAgents config dict that the signal adapter will use.
    # Start from the full DEFAULT_CONFIG (which includes .env + env-var
    # overrides) and layer CLI flags on top.
    ta_config = DEFAULT_CONFIG.copy()
    ta_config["llm_provider"] = args.llm_provider
    ta_config["quick_think_llm"] = args.quick_model
    ta_config["deep_think_llm"] = args.deep_model
    if args.backend_url:
        ta_config["backend_url"] = args.backend_url

    logger.info("=== Competition Trading Bot ===")
    logger.info("Instruments: %s", ", ".join(instruments))
    logger.info("Mode: %s", "DRY-RUN" if args.dry_run else "LIVE")
    logger.info("LLM provider: %s", ta_config["llm_provider"])
    logger.info("  quick model: %s", ta_config["quick_think_llm"])
    logger.info("  deep model:  %s", ta_config["deep_think_llm"])
    if ta_config.get("backend_url"):
        logger.info("  backend:     %s", ta_config["backend_url"])
    logger.info("Max positions: %d", args.max_positions)
    if args.no_llm:
        logger.info("LLM signals: DISABLED (--no-llm, indicator-only)")

    # Wire components
    broker = MockBrokerClient(instruments=instruments)
    firewall = ExecutionEngine()
    signal_adapter = SignalAdapter(config=ta_config)

    # Always create state bus for persistence (analysis progress, trades, etc.)
    # This allows web-only dashboard to read history even when engine runs separately
    from competition.state_bus import CompetitionStateBus
    state_bus = CompetitionStateBus()

    if args.web:
        logger.info("Web dashboard: starting API server on http://0.0.0.0:8000")
        logger.info("Frontend: cd frontend && npm run dev   (then open http://localhost:5173/competition)")

        def _run_web():
            import uvicorn
            from web.main import app
            # Inject the state bus so the API can read it
            app.state.competition_bus = state_bus
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

        threading.Thread(target=_run_web, daemon=True).start()

    engine = CompetitionEngine(
        broker=broker,
        instruments=instruments,
        signal_adapter=signal_adapter,
        firewall=firewall,
        dry_run=args.dry_run,
        no_llm=args.no_llm,
        state_bus=state_bus,
    )

    # Graceful shutdown on SIGINT / SIGTERM
    def handle_shutdown(signum, frame):
        logger.info("Received signal %d — stopping engine", signum)
        engine.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    engine.start()


if __name__ == "__main__":
    main()
