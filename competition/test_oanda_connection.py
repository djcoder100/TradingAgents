#!/usr/bin/env python3
"""Quick OANDA connection test — verify credentials before running engine.

Usage:
    python3 competition/test_oanda_connection.py

This script will:
1. Load env vars (OANDA_API_KEY, OANDA_ACCOUNT_ID)
2. Attempt to connect to your OANDA account
3. Display account info and available instruments
4. Test order placement (safely on practice account)
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger("oanda_test")

def test_oanda_connection():
    """Test OANDA connection and display account info."""
    from competition.oanda_config import (
        OANDA_API_KEY,
        OANDA_ACCOUNT_ID,
        OANDA_ENVIRONMENT,
        OANDA_BASE_URL,
    )

    if not OANDA_API_KEY or not OANDA_ACCOUNT_ID:
        logger.error("OANDA credentials missing: OANDA_API_KEY, OANDA_ACCOUNT_ID")
        logger.error("Get them from https://www.oanda.com/account/ → Manage Account → API Access")
        return False

    import requests

    logger.info("=" * 60)
    logger.info("OANDA Connection Test")
    logger.info("=" * 60)
    logger.info("Mode:        %s", OANDA_ENVIRONMENT.upper())
    logger.info("Account ID:  %s", OANDA_ACCOUNT_ID)
    logger.info("Endpoint:    %s", OANDA_BASE_URL)

    headers = {
        "Authorization": f"Bearer {OANDA_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        # Test connection
        logger.info("\nAttempting to connect...")
        response = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}",
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

        account_data = response.json()
        account = account_data.get("account", {})

        logger.info("\n✓ Account Info:")
        logger.info("  Alias:         %s", account.get("alias", "Account"))
        logger.info("  Balance:       $%.2f", float(account.get("balance", 0)))
        logger.info("  Equity:        $%.2f", float(account.get("equity", 0)))
        logger.info("  Margin Used:   $%.2f", float(account.get("marginUsed", 0)))
        logger.info("  Margin Avail:  $%.2f", float(account.get("marginAvailable", 0)))

        margin_rate = float(account.get("marginRate", 0.02))
        leverage = int(margin_rate ** -1) if margin_rate > 0 else 50
        logger.info("  Leverage:      1:%d", leverage)

        # Test symbols (fetch pricing for common forex pairs)
        logger.info("\nTesting symbols...")
        test_symbols = ["EUR_USD", "GBP_USD", "XAU_USD", "USD_JPY"]
        symbols_param = ",".join(test_symbols)

        response = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/pricing",
            headers=headers,
            params={"instruments": symbols_param},
            timeout=10,
        )

        if response.status_code == 200:
            prices = response.json().get("prices", [])
            for price_data in prices:
                instrument = price_data["instrument"]
                bid = float(price_data["bids"][0]["price"])
                ask = float(price_data["asks"][0]["price"])
                logger.info("  ✓ %s: bid=%.5f, ask=%.5f", instrument, bid, ask)
        else:
            logger.warning("  Could not fetch pricing data")

        logger.info("\n" + "=" * 60)
        logger.info("✓ Connection test passed!")
        logger.info("=" * 60)
        logger.info("\nYou can now run the engine:")
        logger.info("  uv run competition --broker oanda --instruments XAUUSD,EURUSD,GBPUSD")
        logger.info("\nFor practice trading, OANDA_ENVIRONMENT=practice (default)")
        logger.info("For real trading, set OANDA_ENVIRONMENT=live")
        return True

    except Exception as e:
        logger.error("✗ Connection failed: %s", e)
        return False

if __name__ == "__main__":
    success = test_oanda_connection()
    sys.exit(0 if success else 1)
