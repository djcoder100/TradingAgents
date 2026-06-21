# competition/config.py
"""Competition parameters — single source of truth for all limits and settings.

All risk limits are deliberately stricter than the competition's penalty
thresholds to provide a safety buffer against measurement lag and rounding.
"""

from __future__ import annotations

import os
from datetime import timezone

# ---------------------------------------------------------------------------
# Competition schedule (BST = UTC+1)
# ---------------------------------------------------------------------------
COMPETITION_START = "2026-06-21T22:00:00+01:00"  # June 21, 22:00 BST
COMPETITION_END = "2026-06-24T22:00:00+01:00"    # June 24, 22:00 BST
TIMEZONE = timezone.utc  # all internal timestamps in UTC

# ---------------------------------------------------------------------------
# Risk discipline — §13 compliance (stricter than penalty limits)
# ---------------------------------------------------------------------------
MAX_LEVERAGE = 25.0        # penalty at 28x, disqualification at 30x
MAX_MARGIN_PCT = 0.80      # penalty at 90% for 30 continuous minutes

# Competition red-line thresholds (for compliance monitoring / alerts)
LEVERAGE_PENALTY = 28.0    # 20-point deduction if exceeded
LEVERAGE_DISQUALIFY = 30.0  # immediate disqualification
MARGIN_PENALTY_PCT = 0.90  # 20-point deduction if held >30 min
MARGIN_PENALTY_DURATION_S = 1800  # 30 minutes

# ---------------------------------------------------------------------------
# Execution parameters
# ---------------------------------------------------------------------------
POLLING_INTERVAL_S = 7.0          # 5–10s, well under 500 req/s safe harbor
SIGNAL_REFRESH_INTERVAL_S = 900   # re-run TradingAgents every 15 min
MAX_CONCURRENT_POSITIONS = 8      # hard cap on open positions
MIN_15MIN_INTERVALS = 8           # required for full Sharpe score (§7)
TRADINGAGENTS_MAX_INSTRUMENTS = 5 # top N instruments to re-analyze per cycle

# ---------------------------------------------------------------------------
# Position sizing defaults
# ---------------------------------------------------------------------------
DEFAULT_POSITION_PCT = 0.05   # 5% of equity per trade when no explicit size
MAX_POSITION_PCT = 0.12       # 12% max per single position
MIN_ORDER_NOTIONAL = 1000.0   # don't bother with sub-$1k orders

# ---------------------------------------------------------------------------
# Technical indicator parameters (entry/exit timing)
# ---------------------------------------------------------------------------
RSI_OVERSOLD = 40.0       # enter BUY when RSI below this
RSI_OVERBOUGHT = 65.0     # enter SELL when RSI above this
ATR_STOP_MULTIPLIER = 2.0  # trailing stop distance in ATR units
SIGNAL_STALE_S = 1800      # 30 min — signal expired, time-stop exit

# ---------------------------------------------------------------------------
# Instrument list — placeholder until competition system goes live
# ---------------------------------------------------------------------------

# Team A strategy: high-liquidity Forex majors with low intraday volatility.
# Smooth equity curve → low Std → high Sharpe (the 10% score + tie-breaker).
# These pairs have tight bid/ask spreads and deep liquidity around the clock.
TEAM_A_INSTRUMENTS: list[str] = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY",
    "XAUUSD",  # Gold — moderate vol but strong trend signals from TradingAgents
    # BARUSD = HBAR/Hedera per competition clarification. Confirm contract specs at MT5 login.
    "BARUSD",
]

# Full instrument universe (includes crypto — Team B volatility territory).
# Only use this if you accept higher Std and lower Sharpe in exchange for
# higher potential Return. Crypto can spike ±20% in one 15-min interval,
# which will crush your Sharpe Rank even if total return is higher.
ALL_INSTRUMENTS: list[str] = [
    # Forex majors
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
    # Forex crosses
    "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "AUDJPY", "NZDJPY", "CADJPY",
    "GBPCHF", "EURAUD", "EURCAD", "GBPAUD", "GBPCAD", "AUDCAD", "AUDCHF",
    "AUDNZD", "EURNZD", "GBPNZD", "NZDCAD", "NZDCHF",
    # Precious metals
    "XAUUSD", "XAGUSD",
    # Major crypto (high volatility — degrades Sharpe score)
    "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "DOGEUSD",
]

# Default to the Team A conservative set unless overridden via env
DEFAULT_INSTRUMENTS: list[str] = TEAM_A_INSTRUMENTS

# COMPETITION_INSTRUMENTS env var overrides: comma-separated list of tickers.
# Set to "ALL" to use the full universe (accepting Team B volatility risk).
_INSTRUMENT_OVERRIDE = os.environ.get("COMPETITION_INSTRUMENTS")
if _INSTRUMENT_OVERRIDE:
    if _INSTRUMENT_OVERRIDE.strip().upper() == "ALL":
        DEFAULT_INSTRUMENTS = ALL_INSTRUMENTS
    else:
        DEFAULT_INSTRUMENTS = [s.strip() for s in _INSTRUMENT_OVERRIDE.split(",") if s.strip()]

# ---------------------------------------------------------------------------
# TradingAgents config overrides for competition mode
# ---------------------------------------------------------------------------
# Analysts to run: comma-separated list of market, social, news, fundamentals.
# Defaults to market+fundamentals (skip social/news for speed in competition).
# Set COMPETITION_ANALYSTS=market,social,news,fundamentals to run all four.
_VALID_ANALYSTS = {"market", "social", "news", "fundamentals"}
_ANALYSTS_ENV = os.environ.get("COMPETITION_ANALYSTS", "market,social,news,fundamentals")
TA_ANALYSTS = [a.strip() for a in _ANALYSTS_ENV.split(",") if a.strip() in _VALID_ANALYSTS]
if not TA_ANALYSTS:  # never let it be empty
    TA_ANALYSTS = ["market", "fundamentals"]
TA_MAX_DEBATE_ROUNDS = 1
TA_MAX_RISK_ROUNDS = 1
