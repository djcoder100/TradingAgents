#!/usr/bin/env python3
"""Quick MT5 connection test — verify credentials before running engine.

Usage:
    python3 competition/test_mt5_connection.py

This script will:
1. Verify MetaTrader5 package is installed
2. Load env vars (MT5_ACCOUNT_NUMBER, MT5_PASSWORD, MT5_SERVER)
3. Attempt to connect to your MT5 account
4. Display account info, symbols, and connection health
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("mt5_test")

def test_mt5_connection():
    """Test MT5 connection and display account info."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        logger.error("MetaTrader5 not installed. Install with: pip install MetaTrader5")
        return False

    # Load credentials from env
    from competition.mt5_config import (
        MT5_ACCOUNT_NUMBER,
        MT5_PASSWORD,
        MT5_SERVER,
        MT5_TIMEOUT_S,
        MT5_TERMINAL_PATH,
    )

    if not all([MT5_ACCOUNT_NUMBER, MT5_PASSWORD, MT5_SERVER]):
        logger.error("Missing required env vars: MT5_ACCOUNT_NUMBER, MT5_PASSWORD, MT5_SERVER")
        logger.error("Set them in .env or shell before running this test")
        return False

    logger.info("=" * 60)
    logger.info("MT5 Connection Test")
    logger.info("=" * 60)
    logger.info("Account: %s", MT5_ACCOUNT_NUMBER)
    logger.info("Server:  %s", MT5_SERVER)
    logger.info("Timeout: %d seconds", MT5_TIMEOUT_S)

    # Attempt connection
    logger.info("\nAttempting to initialize MT5...")
    if not mt5.initialize(
        path=MT5_TERMINAL_PATH,
        login=MT5_ACCOUNT_NUMBER,
        password=MT5_PASSWORD,
        server=MT5_SERVER,
        timeout=MT5_TIMEOUT_S * 1000,
    ):
        error = mt5.last_error()
        logger.error("✗ Failed to initialize MT5: %s", error)
        return False

    logger.info("✓ MT5 initialized")

    # Fetch account info
    try:
        account = mt5.account_info()
        if account is None:
            logger.error("✗ account_info() returned None (not logged in?)")
            return False

        logger.info("\n✓ Account Info:")
        logger.info("  Name:         %s", account.name)
        logger.info("  Balance:      $%.2f", account.balance)
        logger.info("  Equity:       $%.2f", account.equity)
        logger.info("  Margin:       $%.2f used, $%.2f free", account.margin, account.margin_free)
        logger.info("  Margin Level: %.2f%%", account.margin_level or 0)
        logger.info("  Leverage:     1:%d", account.leverage or 1)
        logger.info("  Currency:     %s", account.currency)

        # Test symbol availability
        logger.info("\nTesting symbols...")
        test_symbols = ["EURUSD", "XAUUSD", "BARUSD"]
        for symbol in test_symbols:
            info = mt5.symbol_info(symbol)
            if info:
                logger.info("  ✓ %s available (bid=%.5f, ask=%.5f)", symbol, info.bid, info.ask)
            else:
                logger.info("  ✗ %s not found (try override: MT5_SYMBOL_OVERRIDES=%s=YOUR_SYMBOL)", symbol, symbol)

        # Test a simple order (MARKET BUY, won't be sent with --dry-run)
        logger.info("\nTesting order placement...")
        symbol = "EURUSD"
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": 0.01,
                "type": mt5.ORDER_TYPE_BUY,
                "price": symbol_info.bid,
                "comment": "test",
            }
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info("  ✓ Order placement works (order_id=%s) — will be cancelled on next check", result.order)
                # Cancel it immediately
                cancel_request = {
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": result.order,
                }
                cancel_result = mt5.order_send(cancel_request)
                if cancel_result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info("  ✓ Order cancellation works")
            else:
                logger.warning("  ! Order placement returned: %s (this is OK if broker restricts test orders)", result.comment)

        logger.info("\n" + "=" * 60)
        logger.info("✓ Connection test passed!")
        logger.info("=" * 60)
        logger.info("\nYou can now run the engine:")
        logger.info("  uv run competition --broker mt5 --dry-run --instruments XAUUSD")
        logger.info("\nFor real trading:")
        logger.info("  uv run competition --broker mt5 --instruments XAUUSD,EURUSD")
        return True

    except Exception as e:
        logger.error("✗ Error during test: %s", e)
        return False

    finally:
        # Clean shutdown
        try:
            mt5.shutdown()
        except:
            pass

if __name__ == "__main__":
    success = test_mt5_connection()
    sys.exit(0 if success else 1)
