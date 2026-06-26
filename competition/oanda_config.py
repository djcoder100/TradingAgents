# competition/oanda_config.py
"""OANDA broker configuration."""

import os

# ============================================================================
# OANDA Connection Parameters (from environment)
# ============================================================================

OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")

# Paper (practice) vs Live trading
OANDA_ENVIRONMENT = os.environ.get("OANDA_ENVIRONMENT", "practice")  # "practice" or "live"

# OANDA endpoints
OANDA_BASE_URL_PRACTICE = "https://api-fxpractice.oanda.com"
OANDA_BASE_URL_LIVE = "https://api-fxtrade.oanda.com"

OANDA_BASE_URL = OANDA_BASE_URL_PRACTICE if OANDA_ENVIRONMENT == "practice" else OANDA_BASE_URL_LIVE

# ============================================================================
# Symbol Mapping (OANDA uses standard Forex/CFD names)
# ============================================================================

# OANDA supports:
# - Forex pairs: EURUSD, GBPUSD, etc. (no suffix)
# - Metals: XAUUSD (gold), XAGUSD (silver)
# - Commodities: WTIUSD (oil), NGAS (natural gas)
# - Indices: SPX500, NATGAS, etc.

OANDA_SYMBOL_OVERRIDES = {}
_overrides_raw = os.environ.get("OANDA_SYMBOL_OVERRIDES", "")
if _overrides_raw:
    for pair in _overrides_raw.split(","):
        if "=" in pair:
            engine_sym, oanda_sym = pair.split("=", 1)
            OANDA_SYMBOL_OVERRIDES[engine_sym.strip()] = oanda_sym.strip()

# Default OANDA symbol mappings (exact match = no suffix)
OANDA_DEFAULT_SYMBOLS = {
    # Forex majors
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
    "USDJPY": "USD_JPY",
    "USDCHF": "USD_CHF",
    "USDCAD": "USD_CAD",
    "AUDUSD": "AUD_USD",
    "NZDUSD": "NZD_USD",

    # Crosses
    "EURGBP": "EUR_GBP",
    "EURJPY": "EUR_JPY",
    "GBPJPY": "GBP_JPY",

    # Metals
    "XAUUSD": "XAU_USD",  # Gold
    "XAGUSD": "XAG_USD",  # Silver

    # HBAR (if OANDA supports it; may need override)
    "BARUSD": "HB_USD",  # Hedera (check broker support)
}

# ============================================================================
# Trading Configuration
# ============================================================================

# OANDA allows fractional lots
ALLOW_FRACTIONAL_LOTS = True

# Default leverage (OANDA defaults to 50:1 for retail, up to 500:1 for pro)
DEFAULT_LEVERAGE = 50

# ============================================================================
# Retry Configuration
# ============================================================================

MAX_RETRY_ATTEMPTS = 3
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 10.0
REQUEST_TIMEOUT_S = 30

# Streaming price updates interval (for position tracking)
PRICING_STREAM_BUFFER_S = 1  # Buffer price updates every 1 second
