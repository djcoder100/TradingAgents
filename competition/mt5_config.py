# competition/mt5_config.py
"""MT5 broker configuration and defaults."""

import os
from typing import Dict, Optional

# ============================================================================
# MT5 Connection Parameters (from environment)
# ============================================================================

MT5_ACCOUNT_NUMBER = int(os.environ.get("MT5_ACCOUNT_NUMBER", 0))
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")
MT5_ACCOUNT_TYPE = os.environ.get("MT5_ACCOUNT_TYPE", "demo")  # demo or live
MT5_TIMEOUT_S = int(os.environ.get("MT5_TIMEOUT_S", "10"))
MT5_TERMINAL_PATH = os.environ.get("MT5_TERMINAL_PATH", None)  # Optional local terminal path

# ============================================================================
# Symbol Mapping (explicit overrides for broker-specific naming)
# ============================================================================

# Parse MT5_SYMBOL_OVERRIDES env var (format: BARUSD=HBAR,CUSTOM=NATIVE)
_overrides_raw = os.environ.get("MT5_SYMBOL_OVERRIDES", "")
MT5_SYMBOL_OVERRIDES: Dict[str, str] = {}
if _overrides_raw:
    for pair in _overrides_raw.split(","):
        if "=" in pair:
            engine_sym, mt5_sym = pair.split("=", 1)
            MT5_SYMBOL_OVERRIDES[engine_sym.strip()] = mt5_sym.strip()

# Default symbol mappings (if broker uses different names)
MT5_DEFAULT_SYMBOLS = {
    # Forex majors (typically use =X suffix on some platforms, none on others)
    # Most MT5 brokers use EURUSD (no suffix), so we use that as default
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "USDCHF": "USDCHF",
    "USDCAD": "USDCAD",
    "AUDUSD": "AUDUSD",
    "NZDUSD": "NZDUSD",

    # Metals
    "XAUUSD": "XAUUSD",  # Gold
    "XAGUSD": "XAGUSD",  # Silver

    # Crypto (if supported by broker)
    "BTCUSD": "BTCUSD",
    "ETHUSD": "ETHUSD",

    # Commodities
    "BARUSD": "BARUSD",  # Hedera (competition note: BARUSD = HBAR per clarification)
}

# ============================================================================
# Order Configuration
# ============================================================================

DEFAULT_ORDER_TYPE = "MARKET"  # MARKET or LIMIT
DEFAULT_SLIPPAGE_PCT = 0.001  # 0.1% for price calculation
DEFAULT_FILL_TIMEOUT_S = 60  # Max time to wait for a limit order to fill

# ============================================================================
# Polling Configuration
# ============================================================================

FILL_POLL_INTERVAL_S = 1  # Check for fills every 1 second
POSITION_SYNC_INTERVAL_S = 5  # Refresh positions every 5 seconds
ACCOUNT_SYNC_INTERVAL_S = 10  # Refresh account state every 10 seconds

# ============================================================================
# Retry Configuration (used by call_with_retry)
# ============================================================================

MAX_RETRY_ATTEMPTS = 3
INITIAL_BACKOFF_S = 2.0
MAX_BACKOFF_S = 30.0

# ============================================================================
# Connection Health Check
# ============================================================================

HEALTH_CHECK_INTERVAL_S = 30  # Query MT5 health every 30 seconds
HEALTH_CHECK_TIMEOUT_S = 5    # Fail health check if no response in 5s
