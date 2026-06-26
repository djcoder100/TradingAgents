# 🚀 START HERE — Manual MT5 Trading

You have a complete automated trading system that **shows you what to trade** and you **manually execute in MT5**.

---

## **30-Second Setup**

```bash
./scripts/start-manual-mt5.sh
```

That's it! Everything starts:
- ✅ Trading engine (generates signals)
- ✅ Dashboard (http://localhost:5173/competition)
- ✅ State service + Web API
- ✅ Browser opens automatically

---

## **How It Works**

### **1. Engine Generates Signal**

Dashboard shows:
```
🟢 BUY XAUUSD 0.10 lots
   Entry: Market (2350.50)
   SL: 2340.00
   TP: 2365.00
```

### **2. You Execute Manually in MT5**

```
Right-click MT5 → New Order
  Symbol: XAUUSD
  Volume: 0.10
  Price: 2350.50
  SL: 2340.00
  TP: 2365.00
  Click: BUY
```

### **3. Dashboard Updates Automatically**

Once MT5 reports the fill, dashboard shows:
```
✓ XAUUSD — 0.10 lots — FILLED
  Entry: 2350.50
  P&L: Real-time tracking
```

---

## **Key Files & Scripts**

| What | Where | Command |
|------|-------|---------|
| **Start Everything** | `scripts/start-manual-mt5.sh` | `./scripts/start-manual-mt5.sh` |
| **Stop Everything** | `scripts/start-manual-mt5.sh` | `./scripts/start-manual-mt5.sh --stop` |
| **Full Manual MT5 Guide** | `MANUAL_MT5_TRADING.md` | `cat MANUAL_MT5_TRADING.md` |
| **Day-Trading Guide** | `DAY_TRADING_GUIDE.md` | `cat DAY_TRADING_GUIDE.md` |
| **Broker Setup** | `BROKER_SETUP.md` | `cat BROKER_SETUP.md` |
| **Alpaca/OANDA/MT5 Quick Start** | `ALPACA_OANDA_MT5_QUICK_START.md` | Read this for broker options |

---

## **The 3 Trading Modes**

### **Mode 1: Fully Automated (Auto-Execute)**

```bash
# OANDA automatically executes all trades
./scripts/start-manual-mt5.sh
# But first, change engine from mock to OANDA:
# uv run competition --broker oanda --web --instruments XAUUSD
```

**Pros**: No manual effort
**Cons**: Trades execute without your verification

### **Mode 2: Manual MT5 (Recommended)**

```bash
# Engine generates signals (mock broker = no auto-execution)
./scripts/start-manual-mt5.sh

# You manually execute in MT5 desktop
# Dashboard auto-detects fills
```

**Pros**: You verify each trade, full control, use real MT5
**Cons**: Takes a few seconds to execute each trade manually

### **Mode 3: Alpaca/Stocks**

```bash
# For stocks/crypto instead of forex
# Edit .env: ALPACA_API_KEY=... ALPACA_API_SECRET=...
./scripts/start-manual-mt5.sh
# But change engine: uv run competition --broker alpaca --web --instruments AAPL,BTC/USD
```

**Pros**: Works on macOS, no MT5 needed
**Cons**: Limited to stocks/crypto

---

## **The Dashboard**

Open: **http://localhost:5173/competition**

Shows in real-time:
- 📊 **Scoreboard**: Return %, Max DD, Sharpe, Equity, Leverage
- 📖 **Signals**: What to trade next (Action, Size, Entry, SL, TP)
- 💰 **Positions**: Open positions with live P&L
- 📈 **Trade History**: All past trades and their results
- ⚙️ **Account**: Balance, margin, leverage

---

## **Expected Daily Flow**

### **Morning (8am)**

```
You:    Run: ./scripts/start-manual-mt5.sh
        Open dashboard
System: Engine starts, generates signals
        State service running
        Web API ready
```

### **Throughout Day (8am - 4pm)**

```
Engine:  Generates signals every 15 minutes
         Example: "BUY XAUUSD 0.10 @ 2350"

You:     Copy signal details
         Open MT5 desktop
         Right-click → New Order
         Enter: XAUUSD, 0.10, 2350, SL: 2340, TP: 2365
         Click BUY

System:  Detects fill in MT5 (1-2 seconds)
         Updates dashboard with P&L
         Tracks position until close
```

### **End of Day (3:50pm)**

```
System: "Liquidating all positions before market close"
You:    Can manually close in MT5, or let system close
Result: Daily P&L summary
        Ready for next day (no overnight risk)
```

---

## **Installation (First Time)**

### **Prerequisites**

- Python 3.11+
- UV package manager (`pip install uv`)
- Node.js (for frontend)
- MetaTrader 5 desktop (if using MT5 manual mode)

### **One-Time Setup**

```bash
cd ~/data/code/github/stealth/TradingAgents

# Install Python dependencies
uv sync

# Install frontend dependencies  
cd frontend && npm install && cd ..

# Make script executable
chmod +x scripts/start-manual-mt5.sh

# You're done!
```

### **Every Day (Start Trading)**

```bash
./scripts/start-manual-mt5.sh
```

---

## **Configuration (Optional)**

Edit `.env` to customize:

```bash
# What to trade
COMPETITION_INSTRUMENTS=XAUUSD,EURUSD,GBPUSD

# Day-trading mode (close all positions at 3:50pm EST)
COMPETITION_DAY_TRADING=true

# Fast signals (no LLM, just technicals)
COMPETITION_NO_LLM=1

# Ports (if already in use)
TRADINGAGENTS_WEB_PORT=8000
VITE_PORT=5173
```

---

## **Common Commands**

```bash
# Start everything
./scripts/start-manual-mt5.sh

# Stop everything
./scripts/start-manual-mt5.sh --stop

# Check what's running
./scripts/start-manual-mt5.sh --status

# See logs
tail -f .logs/engine.log
tail -f .logs/web-api.log

# View dashboard
open http://localhost:5173/competition
```

---

## **Troubleshooting**

### "Port already in use"

```bash
# Find what's using port 8000 (API)
lsof -i :8000

# Change port in .env:
TRADINGAGENTS_WEB_PORT=8001
```

### "MT5 shows order but dashboard doesn't"

→ Dashboard updates every 2 seconds, wait a moment
→ Refresh browser if still not showing

### "No signals appearing"

→ Check logs: `tail -f .logs/engine.log`
→ Make sure COMPETITION_INSTRUMENTS is set correctly in .env

### "Dashboard won't load"

→ Make sure all services started: `./scripts/start-manual-mt5.sh --status`
→ Check: http://localhost:8000/api/health (API should respond)

---

## **Next Steps**

1. **Read Full Manual**: `MANUAL_MT5_TRADING.md` (5 min read)
2. **Start Engine**: `./scripts/start-manual-mt5.sh`
3. **Open Dashboard**: http://localhost:5173/competition
4. **Wait for Signal**: Should appear within 1-2 minutes
5. **Execute in MT5**: Copy signal → MT5 → New Order → Execute

---

## **Features You Now Have**

✅ **Automated signal generation** (LLM or indicators)
✅ **Real-time dashboard** showing all positions
✅ **Day-trading mode** (auto-close at EOD)
✅ **Manual MT5 execution** (you verify before trading)
✅ **Live P&L tracking** (every position monitored)
✅ **Performance metrics** (Sharpe ratio, max DD, return %)
✅ **Trade history** (all trades logged forever)
✅ **Configurable brokers** (Alpaca, OANDA, MT5, Mock)
✅ **Multi-instrument support** (trade Forex, metals, stocks, crypto)
✅ **Risk management** (firewall, position sizing, leverage limits)

---

## **One Command to Rule Them All**

```bash
./scripts/start-manual-mt5.sh
```

Everything starts. Dashboard opens. You trade manually in MT5. System handles everything else.

**Let's trade!** 🚀
