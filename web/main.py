"""FastAPI application entry point for the TradingAgents web API."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.config import get_web_config
from web.api import config, analysis, history, search
from web.services.task_manager import TaskManager

# ── Logging ──────────────────────────────────────────────────────────────────

def _setup_logging():
    """Configure structured logging for the web backend."""
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove default handlers to avoid duplication
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

    logger = logging.getLogger("tradingagents.web")
    logger.info("Web backend logging initialised")

_setup_logging()

logger = logging.getLogger("tradingagents.web.main")


# ── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create and tear down the task manager."""
    web_config = get_web_config()
    tm = TaskManager(ttl_seconds=web_config.get("task_ttl_seconds", 3600))
    app.state.task_manager = tm
    app.state.web_config = web_config
    logger.info("Task manager created (TTL: %ds)", web_config.get("task_ttl_seconds", 3600))
    yield
    logger.info("Shutting down task manager...")
    tm.shutdown()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    web_config = get_web_config()

    app = FastAPI(
        title="TradingAgents API",
        version="0.2.5",
        description="REST API for the TradingAgents multi-agent trading simulation",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=web_config.get("web_cors_origins", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(config.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(analysis.router, prefix="/api")
    app.include_router(search.router, prefix="/api")

    from web.api.competition import router as competition_router
    app.include_router(competition_router, prefix="/api")

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "version": "0.2.5"}

    logger.info("FastAPI app created with %d routers", 4)
    return app


# Create the app instance for uvicorn
app = create_app()
