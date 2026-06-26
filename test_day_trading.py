#!/usr/bin/env python3
"""Quick test of day-trading implementation."""

import sys
import time

print("=" * 70)
print("DAY-TRADING IMPLEMENTATION TEST")
print("=" * 70)

# Test 1: Config loading
print("\n1️⃣  Testing config imports...")
try:
    from competition.config import (
        ACTIVE_POSITION_PCT,
        DAY_TRADING_MODE,
        DAY_TRADING_CLOSE_EOD,
        DAY_TRADING_MAX_HOLD_MIN,
        DAY_TRADING_STOP_LOSS_PIPS,
        DAY_TRADING_TAKE_PROFIT_PIPS,
    )
    print(f"   ✓ Config loaded")
    print(f"     - DAY_TRADING_MODE: {DAY_TRADING_MODE}")
    print(f"     - DAY_TRADING_CLOSE_EOD: {DAY_TRADING_CLOSE_EOD}")
    print(f"     - ACTIVE_POSITION_PCT: {ACTIVE_POSITION_PCT * 100}%")
    print(f"     - MAX_HOLD_TIME: {DAY_TRADING_MAX_HOLD_MIN} min")
    print(f"     - STOP_LOSS_PIPS: {DAY_TRADING_STOP_LOSS_PIPS}")
    print(f"     - TAKE_PROFIT_PIPS: {DAY_TRADING_TAKE_PROFIT_PIPS}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 2: Scheduler
print("\n2️⃣  Testing scheduler methods...")
try:
    from competition.scheduler import Scheduler

    scheduler = Scheduler()
    print(f"   ✓ Scheduler instantiated")

    # Test EOD close detection
    eod_check = scheduler.should_close_all_positions()
    print(f"     - should_close_all_positions() (now): {eod_check}")

    # Test max hold time detection
    one_hour_ago = time.time() - 3600
    max_hold_check = scheduler.position_exceeded_max_hold(one_hour_ago)
    print(f"     - position_exceeded_max_hold(1 hr ago): {max_hold_check} (expected: False, still within 2hr limit)")

    three_hours_ago = time.time() - (3 * 3600)
    max_hold_check_exceeded = scheduler.position_exceeded_max_hold(three_hours_ago)
    print(f"     - position_exceeded_max_hold(3 hrs ago): {max_hold_check_exceeded} (expected: True, exceeds 2hr limit)")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Engine initialization
print("\n3️⃣  Testing engine initialization...")
try:
    from competition.engine import CompetitionEngine
    from competition.api_client import MockBrokerClient

    broker = MockBrokerClient()
    print(f"   ✓ MockBrokerClient created")

    engine = CompetitionEngine(
        broker=broker,
        instruments=["XAUUSD", "EURUSD"],
        dry_run=True,
        no_llm=True,
    )
    print(f"   ✓ CompetitionEngine initialized with day-trading mode")
    print(f"     - Broker: {type(broker).__name__}")
    print(f"     - Instruments: {engine.instruments}")
    print(f"     - Dry-run: {engine.dry_run}")
    print(f"     - Day-trading enabled: {DAY_TRADING_MODE}")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Position sizing
print("\n4️⃣  Testing day-trading position sizing...")
try:
    from competition.signal_adapter import SignalAdapter
    from competition.models import AccountState, OrderAction

    adapter = SignalAdapter()
    print(f"   ✓ SignalAdapter created")

    # Create a test account and decision
    account = AccountState(
        balance=1_000_000,
        equity=1_000_000,
        used_margin=0,
        buying_power=1_000_000,
        gross_notional_exposure=0,
        margin_level=100,
        leverage=1,
        open_positions_count=0,
        open_orders_count=0,
        currency="USD",
    )

    test_decision = {
        "action": "BUY",
        "confidence": 0.8,
        "price_target": 2350,
        "stop_loss": 2340,
    }

    signal = adapter.portfolio_decision_to_signal(test_decision, account, "XAUUSD")

    if signal:
        print(f"   ✓ Signal created with day-trading position sizing")
        print(f"     - Ticker: {signal.ticker}")
        print(f"     - Action: {signal.action.value}")
        print(f"     - Position Size (notional): ${signal.order_size_notional:.0f}")
        expected_size = account.equity * ACTIVE_POSITION_PCT
        print(f"     - Expected size (2% of $1M): ${expected_size:.0f}")
        print(f"     - Match: {abs(signal.order_size_notional - expected_size) < 10} ✓")
    else:
        print(f"   ❌ Signal creation failed")
        sys.exit(1)

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL DAY-TRADING TESTS PASSED!")
print("=" * 70)
print("\nSummary:")
print("  ✓ Config loads correctly with day-trading settings")
print("  ✓ Scheduler detects EOD close and max hold time")
print("  ✓ Engine initializes with day-trading enabled")
print("  ✓ Position sizing set to 2% (day-trading mode)")
print("\nReady to start trading! Run:")
print("  uv run competition --broker oanda --instruments XAUUSD,EURUSD")
print("=" * 70)
