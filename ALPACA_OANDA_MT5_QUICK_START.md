# 🚀 Alpaca + OANDA + MT5 Integration — Quick Start

You now have **4 broker options** working on your macOS machine:

## **What Was Built Today**

✅ **Alpaca Client** — REST API broker adapter (stocks/crypto, macOS-ready)
✅ **OANDA Client** — REST API broker adapter (forex/metals, macOS-ready)  
✅ **MT5 Manual Support** — Dashboard shows what to trade in MT5 desktop
✅ **Mock Broker** — Existing simulation mode (still works)
✅ **Web Broker Selector** — Dashboard shows which broker is active
✅ **Connection Test Scripts** — Verify credentials before running

---

## **Choose Your Path (Pick 1)**

### **Path A: Alpaca (Stocks/Crypto on macOS)**

```bash
# 1. Sign up (free): https://app.alpaca.markets
# 2. Get API key from dashboard
# 3. Add to .env:
ALPACA_API_KEY=PK123...
ALPACA_API_SECRET=secret...
ALPACA_IS_PAPER=true

# 4. Test connection:
python3 competition/test_alpaca_connection.py

# 5. Run engine (auto-executes trades):
uv run competition --broker alpaca --dry-run --instruments AAPL,BTC/USD
# Once confident, remove --dry-run for real trading
uv run competition --broker alpaca --instruments AAPL,BTC/USD

# 6. Dashboard:
http://localhost:5173/competition
```

✅ **Pros**: Free, macOS-ready, full automation, no manual entry needed
❌ **Cons**: 1:1 leverage, US stocks/crypto only

---

### **Path B: OANDA (Forex/Metals on macOS)**

```bash
# 1. Sign up (free): https://www.oanda.com/
# 2. Create API token in Account Manager
# 3. Add to .env:
OANDA_API_KEY=token...
OANDA_ACCOUNT_ID=...
OANDA_ENVIRONMENT=practice

# 4. Test connection:
python3 competition/test_oanda_connection.py

# 5. Run engine (auto-executes trades):
uv run competition --broker oanda --dry-run --instruments XAUUSD,EURUSD
# Once confident, remove --dry-run
uv run competition --broker oanda --instruments XAUUSD,EURUSD,GBPUSD

# 6. Dashboard:
http://localhost:5173/competition
```

✅ **Pros**: 50:1 leverage, forex/metals, perfect for your strategy
❌ **Cons**: Forex focus, not for stocks

---

### **Path C: MT5 Manual Entry (Any Broker)**

```bash
# No API setup needed! Just view dashboard and manually execute in MT5.

# 1. Run engine (generates signals only, no auto-trading):
uv run competition --broker mock --instruments XAUUSD

# 2. Dashboard shows trade recommendations:
http://localhost:5173/competition
# You'll see: "BUY XAUUSD 0.10 lots @ Market | SL: 2340 | TP: 2365"

# 3. Copy the details and manually enter in MT5 Desktop:
# - Right-click Market Watch → New Order
# - Select XAUUSD, set volume 0.10, SL, TP
# - Click Buy
# - Dashboard auto-detects the fill (within 1-2 seconds)
```

✅ **Pros**: Use your existing MT5 account, full control, manual verification
❌ **Cons**: Manual entry required, slower execution

---

### **Path D: Mock (Testing Only)**

```bash
# No setup needed, just run:
uv run competition --mock --dry-run --no-llm --instruments XAUUSD

# Dashboard shows simulated trades (no real money)
http://localhost:5173/competition
```

✅ **Pros**: Zero setup, instant testing, no risk
❌ **Cons**: Simulated prices, no real trading

---

## **What the Dashboard Shows**

For ALL brokers, you'll see the same dashboard at `http://localhost:5173/competition`:

```
┌─────────────────────────────────────────────────────┐
│ Competition Dashboard                               │
│ Broker: Alpaca (paper) | Connected                  │
├─────────────────────────────────────────────────────┤
│ SCOREBOARD                                          │
│ Return: +0.00% | MaxDD: 0.00% | Sharpe: N/A       │
│ Equity: $1,000,000 | Leverage: 0.0x | Margin: 0%  │
├─────────────────────────────────────────────────────┤
│ ACTIVE SIGNALS                                      │
│ ✓ XAUUSD [BUY] 95% confidence                      │
│   Entry: 2350.50 | SL: 2340.00 | TP: 2365.00      │
│                                                     │
│ ✓ EURUSD [SELL] 75% confidence                     │
│   Entry: 1.0850 | SL: 1.0900 | TP: 1.0800         │
├─────────────────────────────────────────────────────┤
│ POSITIONS                                           │
│ XAUUSD [BUY] 0.10 lots | Entry: 2350.50 | P&L: +15 │
├─────────────────────────────────────────────────────┤
│ TRADE HISTORY                                       │
│ 14:30 | XAUUSD | BUY  | 0.10 | $2,350.50 | FILLED  │
│ 14:15 | EURUSD | SELL | 0.20 | $1.0850  | PENDING  │
└─────────────────────────────────────────────────────┘
```

---

## **Key Files**

| File | Purpose |
|------|---------|
| `competition/alpaca_client.py` | Alpaca broker adapter |
| `competition/oanda_client.py` | OANDA broker adapter |
| `competition/alpaca_config.py` | Alpaca config & symbols |
| `competition/oanda_config.py` | OANDA config & symbols |
| `competition/test_alpaca_connection.py` | Test Alpaca credentials |
| `competition/test_oanda_connection.py` | Test OANDA credentials |
| `competition/BROKER_SETUP.md` | Detailed setup guide |
| `competition/main.py` | Updated with `--broker alpaca\|oanda\|mt5\|mock` |
| `.env` | Add ALPACA_* and OANDA_* env vars |

---

## **Command Reference**

```bash
# Alpaca (paper trading)
uv run competition --broker alpaca --dry-run --instruments AAPL,BTC/USD

# Alpaca (live trading)
uv run competition --broker alpaca --instruments AAPL,BTC/USD

# OANDA (practice)
uv run competition --broker oanda --dry-run --instruments XAUUSD,EURUSD

# OANDA (live trading)
uv run competition --broker oanda --instruments XAUUSD,EURUSD,GBPUSD

# MT5 manual (engine shows signals, you execute manually)
uv run competition --broker mock --instruments XAUUSD

# Mock (testing)
uv run competition --broker mock --dry-run --no-llm --instruments XAUUSD

# With dashboard
uv run competition --broker oanda --web --instruments XAUUSD

# With live frontend polling
cd frontend && npm run dev
# Then open: http://localhost:5173/competition
```

---

## **Step-by-Step: Getting Your First Trade**

### **Using OANDA (Recommended for Forex)**

```bash
# Step 1: Create account and get API key
https://www.oanda.com/ → Account Manager → API Access

# Step 2: Add to .env
OANDA_API_KEY=your_token
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENVIRONMENT=practice

# Step 3: Test connection
python3 competition/test_oanda_connection.py

# Step 4: Start with --dry-run to verify
uv run competition --broker oanda --dry-run --instruments XAUUSD --log-level INFO

# Step 5: Watch the logs for signals
# You'll see: "TA [XAUUSD] signal: BUY @ 2350.50"

# Step 6: Open dashboard in another terminal
uv run competition --broker oanda --web --instruments XAUUSD

# Step 7: View at http://localhost:5173/competition
# You'll see the signal appear in "ACTIVE SIGNALS" section

# Step 8: Once confident, remove --dry-run for real trading
uv run competition --broker oanda --instruments XAUUSD,EURUSD
```

---

## **Using Environment Variables**

All broker config is read from `.env`. Edit `.env` to switch brokers:

```bash
# To use Alpaca:
# Uncomment ALPACA_API_KEY and ALPACA_API_SECRET
# Comment out OANDA_API_KEY and OANDA_ACCOUNT_ID

# To use OANDA:
# Uncomment OANDA_API_KEY and OANDA_ACCOUNT_ID
# Comment out ALPACA_API_KEY and ALPACA_API_SECRET

# Then restart the engine:
uv run competition --broker [alpaca|oanda|mock]
```

---

## **Troubleshooting**

### "No API key found for Alpaca"
→ Check `.env` has ALPACA_API_KEY and ALPACA_API_SECRET
→ Run: `echo $ALPACA_API_KEY` (should not be empty)

### "Failed to connect to OANDA"
→ Verify OANDA_API_KEY and OANDA_ACCOUNT_ID in `.env`
→ Run: `python3 competition/test_oanda_connection.py`

### "Order rejected by broker"
→ Check margin is sufficient (broker has min requirements)
→ Verify symbol is tradeable (use test script to check)
→ Try --dry-run mode first

### "Connection timeout"
→ Check internet connection
→ Verify broker API is online
→ Try --log-level DEBUG for details

---

## **Next Steps**

1. **Pick a broker** (Alpaca for stocks, OANDA for forex)
2. **Sign up & get API key** (5 minutes)
3. **Add to `.env`** (1 minute)
4. **Test connection** (1 minute): `python3 competition/test_[broker]_connection.py`
5. **Run with `--dry-run`** (5 minutes): See signals without risk
6. **Switch to live** when confident (remove `--dry-run`)

Ready to trade? Run:

```bash
# OANDA (Forex/Metals)
uv run competition --broker oanda --instruments XAUUSD,EURUSD

# Alpaca (Stocks/Crypto)
uv run competition --broker alpaca --instruments AAPL,BTC/USD

# Dashboard at:
http://localhost:5173/competition
```

---

## **Detailed Guides**

- **BROKER_SETUP.md** — Complete setup for each broker
- **MT5_SETUP.md** — Manual MT5 trading workflow
- **DISTRIBUTED_DEPLOYMENT.md** — Cloud deployment (Heroku, Docker, K8s)

Good luck! 🚀
