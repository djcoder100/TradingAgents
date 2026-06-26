# 🖥️ Manual MT5 Trading — One-Command Setup

Run **one script** that starts everything, then manually execute trades in MetaTrader 5 desktop client.

---

## **Quick Start (30 seconds)**

```bash
# Start everything with one command:
./scripts/start-manual-mt5.sh
```

This starts:
- ✅ State Service (port 9000) — stores live state
- ✅ Engine (mock broker) — generates signals only, no auto-execution
- ✅ Web API (port 8000) — dashboard backend
- ✅ Frontend (port 5173) — live trading dashboard
- ✅ Opens browser to http://localhost:5173/competition

You're done! Dashboard shows signals → you execute manually in MT5.

---

## **What You See on Dashboard**

When a signal is generated, the dashboard shows:

```
📖 SIGNAL RECOMMENDATION
─────────────────────────────────────────────
Action:        BUY
Symbol:        XAUUSD
Size:          0.10 lots
Entry Price:   Market (current mid = 2350.50)
Stop Loss:     2340.00   (10 pips below)
Take Profit:   2365.00   (15 pips above)
Confidence:    85%
Expires In:    28 minutes

👉 ENTER THIS ORDER IN MT5 DESKTOP CLIENT
```

---

## **How to Execute in MT5**

### **Step 1: Open MT5 Desktop**

Launch your MetaTrader 5 application (must be installed locally).

### **Step 2: Create New Order**

```
Right-click in "Market Watch" panel
  ↓
Select "New Order"
  ↓
Order entry dialog opens
```

### **Step 3: Fill in the Details**

Copy from dashboard:

| Field | From Dashboard | Example |
|-------|---|---|
| **Symbol** | Symbol field | XAUUSD |
| **Volume** | Size field | 0.10 |
| **Order Type** | Entry Price (if Market) | Market Execution |
| **Price** | Current bid/ask | 2350.50 |
| **Stop Loss** | SL field | 2340.00 |
| **Take Profit** | TP field | 2365.00 |
| **Comment** | Optional | "TradingAgents signal" |

### **Step 4: Click Buy or Sell**

Click the colored button matching the signal Action (BUY or SELL).

### **Step 5: Confirm**

Click "Send" in the confirmation dialog.

### **Step 6: Watch Dashboard**

The dashboard **auto-detects the fill** within 1-2 seconds:

```
✓ XAUUSD — BUY — 0.10 lots
  Entry:       2350.50
  SL:          2340.00
  TP:          2365.00
  Status:      FILLED ← Updated automatically!
  P&L:         Real-time tracking
```

---

## **Visual Walkthrough**

### **Dashboard Signal View**

```
┌──────────────────────────────────────┐
│ 📖 ACTIVE SIGNALS                    │
├──────────────────────────────────────┤
│                                      │
│ 🟢 XAUUSD [BUY]                     │
│   Entry: Market (2350.50)            │
│   Size: 0.10 lots                    │
│   SL: 2340.00  |  TP: 2365.00       │
│   Confidence: 85%                    │
│   Expires: 28 min                    │
│                                      │
│   👉 Manual Entry in MT5             │
│   ───────────────────────────────    │
│   1. Right-click MT5 → New Order     │
│   2. Symbol: XAUUSD                  │
│   3. Volume: 0.10                    │
│   4. Price: 2350.50                  │
│   5. SL: 2340.00, TP: 2365.00       │
│   6. Click BUY                       │
│                                      │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ ✓ POSITIONS                          │
├──────────────────────────────────────┤
│                                      │
│ ✓ XAUUSD [BUY] 0.10 lots           │
│   Entry:  2350.50                    │
│   Current: 2352.30                   │
│   P&L: +$17.50 (0.07%)              │
│   SL: 2340.00  |  TP: 2365.00       │
│                                      │
└──────────────────────────────────────┘
```

### **MT5 Order Entry Window**

```
┌─ New Order ──────────────────────────┐
│                                      │
│ Symbol:        XAUUSD         ▼      │
│ Order Type:    Market         ▼      │
│ Volume:        0.10                  │
│ Price:         2350.50               │
│                                      │
│ Stop Loss:     2340.00               │
│ Take Profit:   2365.00               │
│ Comment:       TradingAgents signal  │
│                                      │
│ ┌──────────────┬──────────────────┐  │
│ │ [BUY  $$$]   │  [SELL  $$$]     │  │
│ └──────────────┴──────────────────┘  │
│                                      │
└──────────────────────────────────────┘
```

---

## **Command Reference**

### **Start All Services**

```bash
./scripts/start-manual-mt5.sh
```

Starts state service, engine, web API, frontend, and opens browser.

### **Stop All Services**

```bash
./scripts/start-manual-mt5.sh --stop
```

Or press `Ctrl+C` in the terminal where the script is running.

### **Check Status**

```bash
./scripts/start-manual-mt5.sh --status
```

Shows which services are running and their PIDs.

### **View Logs**

```bash
tail -f .logs/engine.log          # See engine decisions
tail -f .logs/state-service.log   # See state updates
tail -f .logs/web-api.log         # See API requests
tail -f .logs/frontend.log        # See frontend errors
```

---

## **Configuration**

All settings come from `.env` file:

```bash
# Instruments to trade (comma-separated)
COMPETITION_INSTRUMENTS=XAUUSD,EURUSD,GBPUSD

# Day-trading mode (auto close at EOD)
COMPETITION_DAY_TRADING=true

# LLM signals or indicators (optional)
COMPETITION_NO_LLM=1

# Ports (change if already in use)
TRADINGAGENTS_WEB_PORT=8000
VITE_PORT=5173
COMPETITION_STATE_SERVICE_PORT=9000
```

**To customize:** Edit `.env` before running the script.

---

## **Manual Trading Workflow**

### **Morning (8am)**

```
08:00 — Engine starts
        Generates signals for XAUUSD, EURUSD, GBPUSD
        Dashboard ready at http://localhost:5173/competition

08:15 — First signal appears
        XAUUSD: BUY 0.10 lots @ 2350.50
        You open MT5, enter the trade manually

08:20 — MT5 order filled
        Dashboard updates: "✓ XAUUSD FILLED at 2350.50"
        Tracking live P&L

09:45 — Take profit hit
        You see: "XAUUSD P&L: +$150 ✓"
        Order auto-closes (or you can close manually in MT5)

10:00 — Next signal appears
        EURUSD: BUY 0.20 lots @ 1.0850
        You repeat: Copy → MT5 → Execute
```

### **Throughout Day**

- ✅ Dashboard shows signal recommendation
- ✅ You manually execute in MT5 within 1-2 minutes
- ✅ Dashboard detects fill automatically
- ✅ Tracks live P&L and position status
- ✅ Shows when to take profit or stop loss
- ✅ Signals refresh every 15 minutes (new opportunities)

### **Before Market Close (3:50pm EST)**

```
15:50 — EOD liquidation timer
        "All positions will close in 10 minutes"

16:00 — Market close
        Engine closes remaining positions (or you do manually in MT5)
        Daily summary: +$450 from 5 trades

16:01 — Ready for next day
        All positions closed, no overnight risk
        Equity updated, Sharpe ratio calculated
```

---

## **Real Example Trade**

### **Signal on Dashboard**

```
🟢 XAUUSD [BUY] 85% confidence
   Size: 0.10 lots
   Entry: Market (2350.50)
   SL: 2340.00
   TP: 2365.00
   Expires: 28 minutes
```

### **You Execute in MT5**

```
1. Right-click Market Watch → New Order
2. Symbol: XAUUSD
3. Volume: 0.10
4. Order Type: Market Execution
5. Stop Loss: 2340.00
6. Take Profit: 2365.00
7. Click [BUY]
8. Confirm
```

### **MT5 Reports Fill**

```
Order #12345678 filled at 2350.52
Volume: 0.10 lots XAUUSD
```

### **Dashboard Updates**

```
✓ XAUUSD — BUY — 0.10 lots
  Entry:      2350.50
  Current:    2350.52  (filled at slightly worse price, normal slippage)
  P&L:        -$2 (slippage)
  Status:     FILLED ✓
  SL:         2340.00
  TP:         2365.00

Time elapsed: 15 seconds
```

### **Hour Later: TP Hit**

```
14:45 — Price hits take profit

MT5 Message:
  "Order #12345678 closed at 2365.00 (take profit)"

Dashboard updates:
  ✓ CLOSED
  P&L: +$150 (0.10 × $1500 / lot)
  Hold time: 1 hour
  Round-trips: +1
```

---

## **Advantages of Manual MT5 Entry**

✅ **Full Control** — You verify before executing
✅ **Emotional Decision-Making** — Can override if price looks wrong
✅ **Real Execution** — Using your real MT5 account
✅ **Slippage Awareness** — You see actual fills
✅ **Flexibility** — Can adjust SL/TP after entry if needed
✅ **Integration** — Dashboard shows ALL your MT5 positions
✅ **Safety** — No accidental auto-executions

---

## **Troubleshooting**

### "Dashboard shows signal but I don't see it in MT5"

→ The signal is **not auto-executed**; you must enter manually
→ Copy the details from dashboard → paste into MT5 order entry
→ It's intentional: you have full control

### "Dashboard shows order but MT5 doesn't"

→ MT5 and dashboard are separate systems
→ Manual entry means you're the bridge
→ Once you execute in MT5, dashboard detects it within 1-2 seconds
→ If it doesn't appear, check MT5 order history (should be there)

### "Position closed in MT5 but dashboard still shows it"

→ Dashboard updates every 2 seconds
→ Wait a moment for it to sync
→ Refresh browser if stuck

### "Services won't start"

→ Check ports are free: `lsof -i :8000` (web), `lsof -i :5173` (frontend), `lsof -i :9000` (state)
→ Check .logs/ files for errors
→ Try stopping with `./scripts/start-manual-mt5.sh --stop` then restart

---

## **Pro Tips**

1. **Keep Two Windows Open**
   - Left: Dashboard (http://localhost:5173/competition)
   - Right: MT5 Desktop Client
   - Easy copy/paste between them

2. **Use Keyboard Shortcut**
   - MT5: Alt+N → New Order (faster than right-click)
   - Copy sizes from dashboard, paste into MT5

3. **Track Win/Loss Rate**
   - Dashboard shows all trades and P&L
   - Monitor your execution vs signal recommendation
   - Improve over time (slippage, timing, etc.)

4. **Time Your Entries**
   - Signals stay active for 30 minutes
   - Try to execute within first 5 minutes (best momentum)
   - Avoid executing right before market close

5. **Adjust SL/TP in MT5**
   - Dashboard suggests SL/TP based on technicals
   - Feel free to adjust in MT5 after entry
   - Tighter SL = more losses but smaller
   - Wider TP = longer holds but higher target

---

## **One-Liner to Start Everything**

```bash
cd ~/data/code/github/stealth/TradingAgents && ./scripts/start-manual-mt5.sh
```

---

**Ready to trade?** Run the script and start manually executing signals in MT5! 🚀
