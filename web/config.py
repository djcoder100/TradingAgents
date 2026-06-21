"""Web-specific configuration that extends the core default_config."""

import os
from tradingagents.default_config import DEFAULT_CONFIG


def get_web_config() -> dict:
    """Return the merged config for the web backend.

    Adds web-specific defaults and applies TRADINGAGENTS_* env overrides
    (already handled by default_config)._ENV_OVERRIDES).
    """
    config = DEFAULT_CONFIG.copy()

    # Web-specific overrides
    config["web_host"] = os.getenv("TRADINGAGENTS_WEB_HOST", "0.0.0.0")
    config["web_port"] = int(os.getenv("TRADINGAGENTS_WEB_PORT", "8000"))
    config["web_cors_origins"] = os.getenv(
        "TRADINGAGENTS_WEB_CORS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")
    config["task_ttl_seconds"] = int(
        os.getenv("TRADINGAGENTS_TASK_TTL", "3600")
    )

    return config
