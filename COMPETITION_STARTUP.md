# Competition Trading Bot — Quick Start Guide

## Overview

The competition bot runs in three separate components:
1. **Engine** — runs TradingAgents LLM analysis + indicator signals
2. **Web API** — serves the dashboard data via HTTP
3. **Frontend** — React dev server for the dashboard UI

The startup scripts manage all three automatically.

---

## Quick Start

### Start Everything (Engine + API + Frontend)
```bash
./scripts/competition-start.sh
```

This will:
- Start the competition engine (dry-run mode by default)
- Start the web API on http://localhost:8000
- Start the frontend dev server on http://localhost:5173
- Open http://localhost:5173/competition in your browser

Press Ctrl+C to stop everything.

### Start Engine Only
```bash
./scripts/competition-start.sh --engine-only
```

Useful for:
- Testing the trading logic without the UI
- Generating trade history for later viewing
- Running overnight without consuming frontend resources

### Start Web-Only Dashboard
```bash
./scripts/competition-start.sh --web-only
```

Useful for:
- Viewing historical trades from a previous run
- Monitoring the engine remotely
- Keeping the dashboard running while restarting the engine

### Check Status
```bash
./scripts/competition-start.sh --status
```

Shows which processes are running and their PIDs.

### Stop Everything
```bash
./scripts/competition-stop.sh
```

Or use the status command:
```bash
./scripts/competition-start.sh --stop
```

---

## Configuration

All configuration is in the `.env` file at the project root. Edit it to customize behavior:

```bash
# Instruments to trade (default: TEAM_A_INSTRUMENTS from config.py)
COMPETITION_INSTRUMENTS=XAUUSD,EURUSD,GBPUSD

# Run in dry-run mode (default: 1 = dry-run only, no real orders)
COMPETITION_DRY_RUN=1

# Skip LLM analysis, use indicator-only signals (speeds up testing)
COMPETITION_NO_LLM=1

# Which analysts to run
COMPETITION_ANALYSTS=market,social,news,fundamentals

# Custom log directory (default: .logs/)
LOG_DIR=.logs

# Custom API and frontend ports
TRADINGAGENTS_WEB_PORT=8000
VITE_PORT=5173
```

The script automatically loads `.env` when it starts, so just edit the file and run:

```bash
./scripts/competition-start.sh
```

### Example 1: Run with Specific Instruments

Edit `.env`:
```ini
COMPETITION_INSTRUMENTS=XAUUSD,EURUSD
```

Then run:
```bash
./scripts/competition-start.sh
```

### Example 2: Run Indicator-Only (Fast, No LLM)

Edit `.env`:
```ini
COMPETITION_NO_LLM=1
```

Then run:
```bash
./scripts/competition-start.sh --engine-only
```

### Example 3: Switch to Live Trading (Caution!)

**Only during competition, when you're confident in your logic:**

Edit `.env`:
```ini
COMPETITION_DRY_RUN=0   # ⚠️ WARNING: Real orders will be placed!
```

Restart:
```bash
./scripts/competition-stop.sh
./scripts/competition-start.sh
```

---

## Viewing Logs

Logs are saved to `.logs/` directory:

```bash
# Watch engine log in real-time
tail -f .logs/competition-engine.log

# Watch API log in real-time
tail -f .logs/competition-web.log

# Watch frontend log in real-time
tail -f .logs/competition-frontend.log

# View all logs
tail -f .logs/*.log
```

---

## Workflow Examples

### Development: Engine + Dashboard in Sync

**Terminal 1** — Start everything:
```bash
./scripts/competition-start.sh
```

**Browser** — Opens to http://localhost:5173/competition automatically.

**Watch logs** in other terminals:
```bash
tail -f .logs/competition-engine.log
tail -f .logs/competition-web.log
```

When you stop the script (Ctrl+C), all processes shut down cleanly.

---

### Testing: Engine Overnight, Dashboard in Morning

**Night** — Start engine only:
```bash
./scripts/competition-start.sh --engine-only
# Can run this in a tmux/screen session and detach
```

**Morning** — View all trades that ran while you slept:
```bash
./scripts/competition-start.sh --web-only
# Open http://localhost:5173/competition
```

All trade history is persisted to `~/.tradingagents/trade_history.json` so you see everything that happened.

---

### Monitoring: Keep Dashboard Running While Restarting Engine

**Terminal 1** — Start web API only:
```bash
./scripts/competition-start.sh --web-only
# This stays running
```

**Terminal 2** — Restart engine as needed:
```bash
./scripts/competition-start.sh --engine-only
# Kill with Ctrl+C and restart anytime
```

The web dashboard in Terminal 1 shows all historical trades and stays connected to whatever engine is running.

---

## Troubleshooting

### Port Already in Use

If you get "Port 8000 is in use" or "Port 5173 is in use":

```bash
# The script will try to kill the old process, but if it fails:
./scripts/competition-start.sh --stop

# Or manually:
lsof -ti:8000 | xargs kill -9   # Kill API
lsof -ti:5173 | xargs kill -9   # Kill frontend
```

### No Data on Dashboard

If the dashboard shows "Waiting for engine data…":

1. Check the engine is running:
   ```bash
   ./scripts/competition-start.sh --status
   ```

2. Check the engine log for errors:
   ```bash
   tail -f .logs/competition-engine.log
   ```

3. Check the API is responding:
   ```bash
   curl http://localhost:8000/api/competition/state
   ```

### Zombie Processes

If processes don't stop cleanly:

```bash
# Check what's running
./scripts/competition-start.sh --status

# Kill by port
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Or kill by name
pkill -f "uv run competition"
pkill -f "vite"
```

---

## Data Persistence

All trade history and analysis is automatically saved to `~/.tradingagents/`:

```bash
~/.tradingagents/
  ├── trade_history.json      # All executed trades
  ├── full_analysis.json       # Full TradingAgents output per run
  └── active_analysis.json     # Latest PM markdown per ticker
```

To reset and start fresh:
```bash
rm -rf ~/.tradingagents/*.json
```

---

## Next Steps

- **View the competition dashboard**: http://localhost:5173/competition (opened automatically)
- **Check engine logs**: `tail -f .logs/competition-engine.log`
- **View all trades**: Click on the "Trade History" section on the dashboard
- **Inspect analysis**: Click on a trade to see the full TradingAgents analysis that produced it
- **Configure instruments**: Edit `COMPETITION_INSTRUMENTS` or modify `competition/config.py`
