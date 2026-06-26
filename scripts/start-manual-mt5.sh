#!/bin/bash
# ============================================================================
# Manual MT5 Trading Mode — One Command to Start Everything
# ============================================================================
#
# This script starts the entire trading system configured for MANUAL entry
# via MetaTrader 5 desktop client.
#
# What happens:
#   1. State Service starts (port 9000) — stores live state
#   2. Engine starts (mock broker) — generates signals only
#   3. Web API starts (port 8000) — provides API endpoints
#   4. Frontend dev server starts (port 5173) — dashboard
#   5. Browser opens to http://localhost:5173/competition
#
# Dashboard shows:
#   📖 Signal: "BUY XAUUSD 0.10 lots @ 2350.50 | SL: 2340 | TP: 2365"
#
# You manually execute in MT5:
#   → Right-click MT5 → New Order
#   → Enter XAUUSD, size 0.10, SL 2340, TP 2365
#   → Click Buy
#   → Dashboard updates automatically when MT5 reports the fill
#
# Usage:
#   ./scripts/start-manual-mt5.sh              Start everything
#   ./scripts/start-manual-mt5.sh --stop       Stop all services
#   ./scripts/start-manual-mt5.sh --status     Show running processes
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ${NC}  $*"; }
log_success() { echo -e "${GREEN}✓${NC}  $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
log_error() { echo -e "${RED}✗${NC}  $*"; }

# Load .env
if [ -f "$PROJECT_DIR/.env" ]; then
  log_info "Loading .env..."
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

# Configuration
PID_FILE="$PROJECT_DIR/.manual-mt5.pids"
LOG_DIR="${LOG_DIR:-.logs}"
mkdir -p "$LOG_DIR"

SERVICE_PORT="${COMPETITION_STATE_SERVICE_PORT:-9000}"
API_PORT="${TRADINGAGENTS_WEB_PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"

SERVICE_LOG="$LOG_DIR/state-service.log"
ENGINE_LOG="$LOG_DIR/engine.log"
WEB_LOG="$LOG_DIR/web-api.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# Configuration for manual MT5 mode
export COMPETITION_DRY_RUN=1  # Never execute real orders
export COMPETITION_NO_LLM=1   # Use fast indicator signals (optional)
export COMPETITION_STATE_SERVICE_URL="http://localhost:$SERVICE_PORT"

# Get instruments from .env or use default
INSTRUMENTS="${COMPETITION_INSTRUMENTS:-XAUUSD,EURUSD,GBPUSD}"

# ============================================================================
# Functions
# ============================================================================

cleanup() {
  log_warn "Stopping all services..."
  if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
      if kill -0 "$pid" 2>/dev/null; then
        log_info "Stopping PID $pid..."
        kill "$pid" 2>/dev/null || true
      fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  log_success "All services stopped"
  exit 0
}

start_service() {
  log_info "Starting State Service (port $SERVICE_PORT)..."
  uv run python3 -m competition.state_service > "$SERVICE_LOG" 2>&1 &
  SERVICE_PID=$!
  echo "$SERVICE_PID" >> "$PID_FILE"
  log_success "State Service PID: $SERVICE_PID"
  sleep 2

  # Health check
  if curl -s http://localhost:$SERVICE_PORT/api/health > /dev/null 2>&1; then
    log_success "State Service is healthy"
  else
    log_error "State Service health check failed"
    exit 1
  fi
}

start_engine() {
  log_info "Starting Engine (mock broker, dry-run mode)..."
  uv run competition --mock --dry-run --instruments "$INSTRUMENTS" \
    --log-level INFO > "$ENGINE_LOG" 2>&1 &
  ENGINE_PID=$!
  echo "$ENGINE_PID" >> "$PID_FILE"
  log_success "Engine PID: $ENGINE_PID"
  sleep 3
}

start_web() {
  log_info "Starting Web API (port $API_PORT)..."
  uv run python3 -m web.main > "$WEB_LOG" 2>&1 &
  WEB_PID=$!
  echo "$WEB_PID" >> "$PID_FILE"
  log_success "Web API PID: $WEB_PID"
  sleep 2

  # Health check
  if curl -s http://localhost:$API_PORT/api/health > /dev/null 2>&1; then
    log_success "Web API is healthy"
  else
    log_error "Web API health check failed"
    exit 1
  fi
}

start_frontend() {
  log_info "Starting Frontend (port $FRONTEND_PORT)..."
  cd "$PROJECT_DIR/frontend"
  npm run dev > "$FRONTEND_LOG" 2>&1 &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" >> "$PID_FILE"
  cd "$PROJECT_DIR"
  log_success "Frontend PID: $FRONTEND_PID"
  sleep 5
}

show_status() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════════╗"
  echo "║           MANUAL MT5 TRADING SYSTEM — STATUS                   ║"
  echo "╚════════════════════════════════════════════════════════════════╝"
  echo ""

  if [ ! -f "$PID_FILE" ]; then
    log_error "No processes running"
    return
  fi

  while IFS= read -r pid; do
    if kill -0 "$pid" 2>/dev/null; then
      PROC_NAME=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
      echo -e "${GREEN}✓${NC}  PID $pid ($PROC_NAME) is running"
    else
      echo -e "${RED}✗${NC}  PID $pid is NOT running"
    fi
  done < "$PID_FILE"

  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "ENDPOINTS:"
  echo "  🌐 Dashboard:     http://localhost:$FRONTEND_PORT/competition"
  echo "  📡 API:           http://localhost:$API_PORT/api"
  echo "  🏪 State Service: http://localhost:$SERVICE_PORT/api/competition/state"
  echo ""
  echo "LOGS:"
  echo "  State Service: $SERVICE_LOG"
  echo "  Engine:        $ENGINE_LOG"
  echo "  Web API:       $WEB_LOG"
  echo "  Frontend:      $FRONTEND_LOG"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
  echo "📖 NEXT STEPS:"
  echo "  1. Open: http://localhost:$FRONTEND_PORT/competition"
  echo "  2. Wait for signals to appear"
  echo "  3. When you see 'BUY XAUUSD 0.10 lots @ 2350.50':"
  echo "     → Copy the details"
  echo "     → Open MT5 Desktop"
  echo "     → Right-click → New Order"
  echo "     → Enter: XAUUSD, 0.10 lots, SL: 2340, TP: 2365"
  echo "     → Click Buy"
  echo "  4. Dashboard updates automatically when MT5 reports the fill"
  echo ""
}

# ============================================================================
# Main
# ============================================================================

trap cleanup SIGINT SIGTERM

# Parse arguments
case "${1:-}" in
  --stop)
    cleanup
    ;;
  --status)
    show_status
    ;;
  *)
    # Start everything
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║    🚀  MANUAL MT5 TRADING MODE — STARTING ALL SERVICES          ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    log_info "Instruments: $INSTRUMENTS"
    log_info "Dry-run mode: ON (safe, no real orders)"
    log_info "Dashboard will show signals for manual MT5 entry"
    echo ""

    # Clear old PID file
    rm -f "$PID_FILE"

    # Start all services
    start_service
    start_engine
    start_web
    start_frontend

    # Show status
    show_status

    log_success "All services started!"
    echo ""
    log_info "Opening dashboard in browser..."

    # Open browser
    if command -v open > /dev/null; then
      open "http://localhost:$FRONTEND_PORT/competition" 2>/dev/null || true
    elif command -v xdg-open > /dev/null; then
      xdg-open "http://localhost:$FRONTEND_PORT/competition" 2>/dev/null || true
    fi

    echo ""
    log_warn "Press Ctrl+C to stop all services"
    echo ""

    # Keep script running
    while true; do
      sleep 1
      # Check if any process died
      if [ -f "$PID_FILE" ]; then
        while IFS= read -r pid; do
          if ! kill -0 "$pid" 2>/dev/null; then
            log_error "Process $pid died! Check logs."
          fi
        done < "$PID_FILE"
      fi
    done
    ;;
esac
