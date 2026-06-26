# competition/mt5_symbol_mapper.py
"""Broker-specific symbol mapping.

Handles the problem where the engine uses canonical tickers (EURUSD, XAUUSD)
but MT5 brokers may use different names (EURUSD, XAUUSD, or HBAR for BARUSD, etc.).

Priority:
  1. Explicit override from MT5_SYMBOL_OVERRIDES env var
  2. Cache lookup (symbol info fetched at startup)
  3. Default mapping
  4. Fallback to engine ticker as-is
"""

import logging
from typing import Optional, Dict, Any

from competition.mt5_config import (
    MT5_SYMBOL_OVERRIDES,
    MT5_DEFAULT_SYMBOLS,
)

logger = logging.getLogger(__name__)


class MT5SymbolMapper:
    """Translates engine tickers to MT5 broker symbols."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}  # ticker → {mt5_symbol, contract_size, tick_size, ...}
        self._mt5 = None

    def set_mt5_module(self, mt5_module) -> None:
        """Set the MT5 module after successful initialization."""
        self._mt5 = mt5_module

    def engine_to_mt5(self, engine_ticker: str) -> str:
        """Translate engine ticker to MT5 broker symbol.

        Returns: MT5 native symbol, or engine_ticker as fallback.
        """
        # 1. Check explicit overrides first (highest priority)
        if engine_ticker in MT5_SYMBOL_OVERRIDES:
            mapped = MT5_SYMBOL_OVERRIDES[engine_ticker]
            logger.debug("Symbol override: %s → %s", engine_ticker, mapped)
            return mapped

        # 2. Check default mapping
        if engine_ticker in MT5_DEFAULT_SYMBOLS:
            return MT5_DEFAULT_SYMBOLS[engine_ticker]

        # 3. Fallback to engine ticker as-is (assume broker uses standard naming)
        logger.debug("No mapping for %s, using as-is", engine_ticker)
        return engine_ticker

    def get_contract_specs(self, engine_ticker: str) -> Optional[Dict[str, Any]]:
        """Get contract specs for this ticker (contract_size, tick_size, volume_min, etc.).

        Returns: dict with keys like {contract_size, tick_size, volume_min, bid, ask}
        Returns None if not found.
        """
        # Check cache first
        if engine_ticker in self._cache:
            return self._cache[engine_ticker]

        # Try to fetch from MT5
        if self._mt5 is None:
            logger.warning("MT5 not initialized, cannot fetch contract specs for %s", engine_ticker)
            return None

        try:
            mt5_symbol = self.engine_to_mt5(engine_ticker)
            symbol_info = self._mt5.symbol_info(mt5_symbol)

            if symbol_info is None:
                logger.warning("MT5: symbol_info returned None for %s (mapped to %s)", engine_ticker, mt5_symbol)
                return None

            specs = {
                "engine_ticker": engine_ticker,
                "mt5_symbol": mt5_symbol,
                "contract_size": getattr(symbol_info, "trade_contract_size", 1.0),
                "tick_size": getattr(symbol_info, "point", 0.0001),
                "volume_min": getattr(symbol_info, "volume_min", 0.01),
                "volume_max": getattr(symbol_info, "volume_max", 100.0),
                "volume_step": getattr(symbol_info, "volume_step", 0.01),
                "bid": getattr(symbol_info, "bid", None),
                "ask": getattr(symbol_info, "ask", None),
            }

            # Cache it
            self._cache[engine_ticker] = specs
            logger.debug("Cached contract specs for %s: contract_size=%.2f, tick=%.6f",
                        engine_ticker, specs["contract_size"], specs["tick_size"])
            return specs

        except Exception as e:
            logger.error("Failed to fetch contract specs for %s: %s", engine_ticker, e)
            return None

    def preload_symbols(self, engine_tickers: list[str]) -> None:
        """Pre-fetch contract specs for a list of symbols at startup."""
        if self._mt5 is None:
            logger.warning("MT5 not initialized, skipping preload")
            return

        logger.info("Preloading contract specs for %d symbols...", len(engine_tickers))
        for ticker in engine_tickers:
            specs = self.get_contract_specs(ticker)
            if specs:
                logger.info("  ✓ %s (MT5: %s, contract_size=%.2f)",
                           ticker, specs["mt5_symbol"], specs["contract_size"])
            else:
                logger.warning("  ✗ %s — symbol not found on broker", ticker)
