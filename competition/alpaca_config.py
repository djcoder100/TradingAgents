# competition/alpaca_config.py
"""Alpaca broker configuration."""

import os

# ============================================================================
# Alpaca Connection Parameters (from environment)
# ============================================================================

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.environ.get("ALPACA_API_SECRET", "")

# Paper (paper-api) vs Live (api) trading
ALPACA_IS_PAPER = os.environ.get("ALPACA_IS_PAPER", "true").lower() in ("true", "1", "yes")

# Alpaca endpoints
ALPACA_BASE_URL_PAPER = "https://paper-api.alpaca.markets"
ALPACA_BASE_URL_LIVE = "https://api.alpaca.markets"
ALPACA_DATA_BASE_URL = "https://data.alpaca.markets"

ALPACA_BASE_URL = ALPACA_BASE_URL_PAPER if ALPACA_IS_PAPER else ALPACA_BASE_URL_LIVE

# ============================================================================
# Symbol Mapping (Alpaca uses standard US stock tickers)
# ============================================================================

# Alpaca supports:
# - US stocks: AAPL, MSFT, etc.
# - Forex: EURUSD=X (note the =X suffix on Alpaca)
# - Crypto: BTC/USD, ETH/USD (native format)
# - Commodities: GC=F (gold futures), SI=F (silver), etc.

ALPACA_SYMBOL_OVERRIDES = {}
_overrides_raw = os.environ.get("ALPACA_SYMBOL_OVERRIDES", "")
if _overrides_raw:
    for pair in _overrides_raw.split(","):
        if "=" in pair:
            engine_sym, alpaca_sym = pair.split("=", 1)
            ALPACA_SYMBOL_OVERRIDES[engine_sym.strip()] = alpaca_sym.strip()

# Default Alpaca symbol mappings
ALPACA_DEFAULT_SYMBOLS = {
    # Forex (Alpaca uses =X suffix)
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
    "USDCAD": "USDCAD=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",

    # Metals (Alpaca uses futures symbol mapping via polygon)
    "XAUUSD": "GC=F",  # Gold
    "XAGUSD": "SI=F",  # Silver

    # Crypto (native format, no suffix)
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",

    # HBAR (Hedera - check if Alpaca supports)
    # May need override: MT5_SYMBOL_OVERRIDES=BARUSD=HBAR
}

# ============================================================================
# Trading Configuration
# ============================================================================

# Alpaca allows fractional shares
ALLOW_FRACTIONAL_SHARES = True

# Market hours (for order timing)
MARKET_OPEN_HOUR = 9  # EST
MARKET_CLOSE_HOUR = 16  # EST

# ============================================================================
# Retry Configuration
# ============================================================================

MAX_RETRY_ATTEMPTS = 3
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 10.0
REQUEST_TIMEOUT_S = 30
