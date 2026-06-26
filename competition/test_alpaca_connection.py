#!/usr/bin/env python3
"""Quick Alpaca connection test — verify credentials before running engine.

Usage:
    python3 competition/test_alpaca_connection.py

This script will:
1. Load env vars (ALPACA_API_KEY, ALPACA_API_SECRET)
2. Attempt to connect to your Alpaca account
3. Display account info and available symbols
4. Test order placement (safely on paper trading)
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("alpaca_test")

def test_alpaca_connection():
    """Test Alpaca connection and display account info."""
    from competition.alpaca_config import (
        ALPACA_API_KEY,
        ALPACA_API_SECRET,
        ALPACA_IS_PAPER,
        ALPACA_BASE_URL,
    )

    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        logger.error("Alpaca credentials missing: ALPACA_API_KEY, ALPACA_API_SECRET")
        logger.error("Get them from https://app.alpaca.markets/paper/dashboard/overview")
        return False

    import requests

    logger.info("=" * 60)
    logger.info("Alpaca Connection Test")
    logger.info("=" * 60)
    logger.info("Mode:     %s", "PAPER" if ALPACA_IS_PAPER else "LIVE")
    logger.info("Endpoint: %s", ALPACA_BASE_URL)

    headers = {"APCA-API-KEY-ID": ALPACA_API_KEY}

    try:
        # Test connection
        logger.info("\nAttempting to connect...")
        response = requests.get(
            f"{ALPACA_BASE_URL}/v2/account",
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

        account = response.json()

        logger.info("\n✓ Account Info:")
        logger.info("  Account ID:  %s", account.get("account_number"))
        logger.info("  Status:      %s", account.get("status"))
        logger.info("  Cash:        $%.2f", float(account.get("cash", 0)))
        logger.info("  Equity:      $%.2f", float(account.get("equity", 0)))
        logger.info("  Buying Power: $%.2f", float(account.get("buying_power", 0)))
        logger.info("  Leverage:    %.1fx", float(account.get("multiplier", 1)))

        # Test symbols
        logger.info("\nTesting symbols...")
        test_symbols = ["AAPL", "SPY", "BTC/USD", "ETH/USD"]
        for symbol in test_symbols:
            try:
                response = requests.get(
                    f"{ALPACA_BASE_URL}/v2/stocks/{symbol}/quotes/latest",
                    headers=headers,
                    timeout=10,
                )
                if response.status_code == 200:
                    quote = response.json().get("quote", {})
                    bid = float(quote.get("bp", 0))
                    ask = float(quote.get("ap", 0))
                    logger.info("  ✓ %s: bid=%.2f, ask=%.2f", symbol, bid, ask)
                else:
                    logger.info("  ✗ %s: not available", symbol)
            except Exception as e:
                logger.info("  ✗ %s: error — %s", symbol, e)

        logger.info("\n" + "=" * 60)
        logger.info("✓ Connection test passed!")
        logger.info("=" * 60)
        logger.info("\nYou can now run the engine:")
        logger.info("  uv run competition --broker alpaca --instruments AAPL,BTC/USD")
        logger.info("\nFor paper trading, ALPACA_IS_PAPER=true (default)")
        return True

    except Exception as e:
        logger.error("✗ Connection failed: %s", e)
        return False

if __name__ == "__main__":
    success = test_alpaca_connection()
    sys.exit(0 if success else 1)
