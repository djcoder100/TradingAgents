# Broker Setup Guide

Quick start for Alpaca, OANDA, and MT5. Choose based on what you want to trade.

## **Quick Comparison**

| Broker | Best For | Leverage | Cost | Setup Time |
|--------|----------|----------|------|-----------|
| **Alpaca** | Stocks & Crypto (US) | 1:1 (intraday up to 4:1) | Free | 5 min |
| **OANDA** | Forex & Metals | 50:1 | Free | 5 min |
| **MT5 Desktop** | Manual trading with any broker | Broker-specific | Varies | 10 min |
| **Mock** | Testing & Development | 30:1 | Free | 0 min |

---

## **1. Alpaca (Stocks & Crypto)**

Perfect for trading US stocks and crypto. Free account, paper trading available.

### Setup (5 minutes)

```bash
# 1. Get API key from https://app.alpaca.markets/paper/dashboard/overview
#    (you'll need to sign up for a free account)

# 2. Add to .env:
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here
ALPACA_IS_PAPER=true   # Set to false for live trading

# 3. Test connection:
python3 competition/test_alpaca_connection.py

# 4. Run engine:
uv run competition --broker alpaca --instruments AAPL,MSFT,BTC/USD

# 5. Dashboard:
http://localhost:5173/competition
```

### Supported Instruments

- **US Stocks**: AAPL, MSFT, GOOGL, TSLA, AMZN, NVDA, SPY, QQQ, etc.
- **Crypto**: BTC/USD, ETH/USD, DOGE/USD
- **ETFs**: SPY, QQQ, IVV, VOO

### Notes

- No leverage for stocks (1:1)
- Fractional shares supported
- Paper trading (free) with unlimited funds
- Great for testing strategy without risk

### Switch to Live Trading

```bash
# Change in .env:
ALPACA_IS_PAPER=false

# Warning: This sends REAL orders. Start with --dry-run first:
uv run competition --broker alpaca --dry-run --instruments AAPL

# Once confident:
uv run competition --broker alpaca --instruments AAPL,BTC/USD
```

---

## **2. OANDA (Forex & Metals)**

Perfect for your strategy (EURUSD, GBPUSD, XAUUSD). 50:1 leverage for Forex.

### Setup (5 minutes)

```bash
# 1. Create free account at https://www.oanda.com/
#    → Login → Account Manager → Manage Account → API Access
#    → Create Personal Access Token

# 2. Add to .env:
OANDA_API_KEY=your_token_here
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENVIRONMENT=practice   # practice or live

# 3. Test connection:
python3 competition/test_oanda_connection.py

# 4. Run engine:
uv run competition --broker oanda --instruments XAUUSD,EURUSD,GBPUSD

# 5. Dashboard:
http://localhost:5173/competition
```

### Supported Instruments

- **Forex Majors**: EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD
- **Forex Crosses**: EURGBP, EURJPY, GBPJPY, GBPCHF
- **Metals**: XAUUSD (Gold), XAGUSD (Silver)
- **Other**: Natural gas, Oil, Indices

### Leverage & Sizing

- 50:1 leverage for most pairs
- Typical spread: 1-3 pips on majors
- Minimum trade: 0.01 lots

### Switch to Live Trading

```bash
# Change in .env:
OANDA_ENVIRONMENT=live

# Warning: This uses REAL money. Start with --dry-run:
uv run competition --broker oanda --dry-run --instruments XAUUSD

# Once confident:
uv run competition --broker oanda --instruments XAUUSD,EURUSD,GBPUSD
```

---

## **3. MetaTrader5 Desktop (Manual Trading)**

Use MT5 desktop client to manually execute trades that the engine recommends.

### When to Use MT5

- ✅ You have MetaTrader5 installed
- ✅ Your broker uses MT5
- ✅ You want to stay in MT5 and enter trades manually
- ✅ You want full control over execution

### Workflow

1. **Engine generates signal** (e.g., BUY XAUUSD 0.10 lots)
2. **Dashboard displays it** in "📖 Manual Trade Instructions"
3. **You copy the details** from the dashboard
4. **You enter in MT5 Desktop** manually
5. **Dashboard updates** when MT5 reports the fill

### Manual Entry in MT5

When you see a trade recommendation on the dashboard:

```
🖥️  MANUAL TRADE INSTRUCTION
────────────────────────────
Action:       BUY
Symbol:       XAUUSD
Size:         0.10 lots
Entry Price:  Market (current bid/ask)
Stop Loss:    2340.00
Take Profit:  2365.00
────────────────────────────
👉 Enter this order in MT5 Desktop Client
```

**Steps to enter in MT5:**

1. Open MT5 Desktop
2. Right-click in Market Watch → New Order
3. Select symbol: XAUUSD
4. Set Order Type: Market Execution (immediate fill)
5. Set Volume: 0.10
6. Set Stop Loss: 2340.00
7. Set Take Profit: 2365.00
8. Click "Buy" or "Sell"
9. Dashboard will auto-detect the fill (within 1-2 seconds)

### Dashboard Will Show

After you execute in MT5, the dashboard updates:

```
✓ XAUUSD — BUY — 0.10 lots
  Filled at: 2350.52
  Entry:     2350.52
  SL:        2340.00
  TP:        2365.00
  Status:    FILLED
```

---

## **Choosing Which Broker to Use**

### Use **Alpaca** if you want to trade:
- US stocks (AAPL, MSFT, Tesla, etc.)
- US crypto (Bitcoin, Ethereum)
- Automated execution (no manual entry needed)
- Paper trading to test strategy risk-free

### Use **OANDA** if you want to trade:
- Forex pairs (EURUSD, GBPUSD, etc.)
- Metals (Gold, Silver)
- High leverage (50:1 for Forex)
- Real money or practice account
- Automated execution (API places orders)

### Use **MT5 Manual** if you want to:
- Keep your existing MT5 setup
- Manually execute recommended trades
- Stay in MT5 desktop client
- Have full control over every entry

### Use **Mock** if you want to:
- Test the system locally without API keys
- Develop and debug strategies
- Run backtests
- No account needed

---

## **Environment Variable Reference**

### Alpaca
```bash
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
ALPACA_IS_PAPER=true  # paper trading
```

### OANDA
```bash
OANDA_API_KEY=your_token
OANDA_ACCOUNT_ID=your_account
OANDA_ENVIRONMENT=practice  # practice or live
```

### MT5
```bash
MT5_ACCOUNT_NUMBER=123456
MT5_PASSWORD=your_password
MT5_SERVER=your_broker_server
MT5_ACCOUNT_TYPE=demo  # demo or live
```

### Mock (no env vars needed)
```bash
# Just run:
uv run competition --broker mock --dry-run
```

---

## **Trading on macOS**

**Alpaca**: ✅ Full support via REST API
**OANDA**: ✅ Full support via REST API
**MT5**: ❌ Desktop client Windows-only, but you can manually trade manually by viewing dashboard

---

## **Testing Before Going Live**

For ANY broker, always test with `--dry-run` first:

```bash
# Alpaca test
uv run competition --broker alpaca --dry-run --instruments AAPL

# OANDA test
uv run competition --broker oanda --dry-run --instruments XAUUSD

# MT5 manual test (just shows recommendations)
# No --dry-run needed; manually execute in MT5 instead
```

`--dry-run` mode:
- ✅ Runs full analysis pipeline
- ✅ Generates trade signals
- ❌ Does NOT send orders to broker
- ✅ Shows what WOULD be traded in dashboard
- ✅ No risk, no losses, testing only

---

## **Next Steps**

1. **Choose a broker** based on the table above
2. **Run the setup command** (5 minutes)
3. **Test connection** with the provided test script
4. **Run with `--dry-run`** to verify signal generation
5. **Switch to live** when confident

Questions? Check the logs:
```bash
# See detailed connection/order logs:
uv run competition --broker oanda --log-level DEBUG
```

---

## **Support**

If you hit issues:

1. **Test connection**: `python3 competition/test_[broker]_connection.py`
2. **Check logs**: Add `--log-level DEBUG`
3. **Verify env vars**: `echo $ALPACA_API_KEY` (should not be empty)
4. **Verify broker**: `uv run competition --broker alpaca` (shows "Alpaca" in startup logs)
