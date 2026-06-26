#!/bin/bash
# ============================================================================
# Manual MT5 Trading Mode — Print Commands for Manual Terminal Startup
# ============================================================================
#
# This script prints the exact commands you need to run in separate terminals.
# Much simpler than automated startup — you see logs in each terminal clearly.
#
# Usage:
#   ./scripts/start-manual.sh
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

clear

cat << 'EOF'
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║          🚀  MANUAL MT5 TRADING — START IN SEPARATE TERMINALS              ║
║                                                                            ║
║  Open 4 new terminal tabs/windows and run ONE command in each, in order:   ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

EOF

cat << 'EOF'
┌─────────────────────────────────────────────────────────────────────────┐
│ TERMINAL 1 — STATE SERVICE (Port 9000)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  cd ~/data/code/github/stealth/TradingAgents                            │
│  uv run python3 -m competition.state_service                            │
│                                                                         │
│  ✓ You'll see: "Server started on 0.0.0.0:9000"                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

EOF

cat << 'EOF'
┌─────────────────────────────────────────────────────────────────────────┐
│ TERMINAL 2 — WEB API (Port 8000)                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  cd ~/data/code/github/stealth/TradingAgents                            │
│  uv run uvicorn web.main:app --host 0.0.0.0 --port 8000                │
│                                                                         │
│  ✓ You'll see: "Application startup complete"                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

EOF

cat << 'EOF'
┌─────────────────────────────────────────────────────────────────────────┐
│ TERMINAL 3 — ENGINE (Generates signals)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  cd ~/data/code/github/stealth/TradingAgents                            │
│  uv run competition --mock --dry-run --instruments XAUUSD --log-level   │
│  INFO                                                                    │
│                                                                         │
│  ✓ You'll see: "TA [XAUUSD] signal: BUY @ 2350.50"                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

EOF

cat << 'EOF'
┌─────────────────────────────────────────────────────────────────────────┐
│ TERMINAL 4 — FRONTEND DEV SERVER (Port 5173)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  cd ~/data/code/github/stealth/TradingAgents/frontend                   │
│  npm run dev                                                            │
│                                                                         │
│  ✓ You'll see: "VITE v5.0.0 ready in XXX ms"                           │
│  ✓ It will auto-open browser, or visit: http://localhost:5173/compe... │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

EOF

cat << 'EOF'

╔════════════════════════════════════════════════════════════════════════════╗
║ THEN OPEN IN BROWSER:                                                      ║
║                                                                            ║
║   http://localhost:5173/competition                                        ║
║                                                                            ║
║ You'll see the live trading dashboard with:                                ║
║   📊 Scoreboard (Return %, MaxDD, Sharpe, Leverage, etc.)                 ║
║   📖 Signals (What to trade next)                                          ║
║   💰 Positions (Open positions with live P&L)                              ║
║   📈 Trade History (All executed trades)                                   ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

EOF

cat << 'EOF'

═══════════════════════════════════════════════════════════════════════════

LOGS IN EACH TERMINAL:

  Terminal 1 (State Service):
    ✓ Connection requests from engine and web API
    ✓ State update logs

  Terminal 2 (Web API):
    ✓ GET /api/competition/state requests
    ✓ Request latencies

  Terminal 3 (Engine):
    ✓ Signal generation ("TA [XAUUSD] signal: BUY")
    ✓ Position tracking
    ✓ Analysis progress
    ✓ Scoring metrics every 15 minutes

  Terminal 4 (Frontend):
    ✓ Vite dev server logs
    ✓ Hot module reload notifications

═══════════════════════════════════════════════════════════════════════════

MANUAL MT5 TRADING WORKFLOW:

  1. Look at the dashboard: http://localhost:5173/competition
  2. See the signal recommendation (e.g., "BUY XAUUSD 0.10 @ 2350.50")
  3. Copy the details
  4. Open MT5 Desktop Client
  5. Right-click Market Watch → New Order
  6. Enter: Symbol, Volume, Price, SL, TP
  7. Click BUY or SELL
  8. Dashboard auto-detects the fill (1-2 second delay)

═══════════════════════════════════════════════════════════════════════════

TO STOP ALL SERVICES:

  Press Ctrl+C in each terminal window (in any order)

═══════════════════════════════════════════════════════════════════════════

EOF
