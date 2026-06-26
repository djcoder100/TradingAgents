#!/bin/bash
# ============================================================================
# Manual MT5 Trading Mode — Start Everything with Live Log Tailing
# ============================================================================
#
# Enhanced version of start-manual-mt5.sh that also shows live logs
# as services start up.
#
# Usage:
#   ./scripts/start-with-logs.sh              # Start everything + show logs
#   ./scripts/start-with-logs.sh --stop       # Stop all services
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
CYAN='\033[0;36m'
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
export COMPETITION_DRY_RUN=1
export COMPETITION_NO_LLM=1
export COMPETITION_STATE_SERVICE_URL="http://localhost:$SERVICE_PORT"

INSTRUMENTS="${COMPETITION_INSTRUMENTS:-XAUUSD,EURUSD,GBPUSD}"

# ============================================================================
# Functions
# ============================================================================

cleanup() {
  log_warn "Stopping all services..."

  # Kill tail processes if they exist
  jobs -p | xargs -r kill 2>/dev/null || true

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

show_logs() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════════╗"
  echo "║                    LIVE SERVICE LOGS                           ║"
  echo "║              (Press Ctrl+C to stop log tailing)                ║"
  echo "╚════════════════════════════════════════════════════════════════╝"
  echo ""

  # Color-code log output
  (
    # State Service
    tail -f "$SERVICE_LOG" | sed "s/^/${CYAN}[STATE]${NC} /" &
    STATE_TAIL_PID=$!

    # Engine
    tail -f "$ENGINE_LOG" | sed "s/^/${GREEN}[ENGINE]${NC} /" &
    ENGINE_TAIL_PID=$!

    # Web API
    tail -f "$WEB_LOG" | sed "s/^/${BLUE}[API]${NC} /" &
    WEB_TAIL_PID=$!

    # Frontend
    tail -f "$FRONTEND_LOG" | sed "s/^/${YELLOW}[FRONTEND]${NC} /" &
    FRONTEND_TAIL_PID=$!

    # Wait for any tail to finish (they run forever)
    wait
  ) &
  TAIL_GROUP_PID=$!

  # After a few seconds, show status in background
  sleep 10
  echo ""
  echo "╔════════════════════════════════════════════════════════════════╗"
  echo "║                    SERVICES RUNNING                            ║"
  echo "╚════════════════════════════════════════════════════════════════╝"
  echo ""
  echo -e "${GREEN}✓${NC}  Dashboard: ${CYAN}http://localhost:$FRONTEND_PORT/competition${NC}"
  echo -e "${GREEN}✓${NC}  API:       ${CYAN}http://localhost:$API_PORT/api${NC}"
  echo -e "${GREEN}✓${NC}  State:     ${CYAN}http://localhost:$SERVICE_PORT/api/competition/state${NC}"
  echo ""
  echo "Instruments: $INSTRUMENTS"
  echo "Mode: Day-trading (${COMPETITION_DAY_TRADING:-unset})"
  echo ""
  echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
  echo ""

  # Keep tail running
  wait $TAIL_GROUP_PID 2>/dev/null || true
}

# ============================================================================
# Main
# ============================================================================

trap cleanup SIGINT SIGTERM

case "${1:-}" in
  --stop)
    cleanup
    ;;
  *)
    # Start everything
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║    🚀  MANUAL MT5 TRADING MODE — STARTING ALL SERVICES          ║"
    echo "║           (with live log tailing)                              ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    log_info "Instruments: $INSTRUMENTS"
    log_info "Dry-run mode: ON (safe, no real orders)"
    log_info "Dashboard will show signals for manual MT5 entry"
    echo ""

    # Clear old PID file
    rm -f "$PID_FILE"

    # Clear old logs
    rm -f "$SERVICE_LOG" "$ENGINE_LOG" "$WEB_LOG" "$FRONTEND_LOG"

    # Start all services
    start_service
    start_engine
    start_web
    start_frontend

    log_success "All services started!"

    # Open browser
    if command -v open > /dev/null; then
      log_info "Opening dashboard in browser..."
      open "http://localhost:$FRONTEND_PORT/competition" 2>/dev/null || true
    elif command -v xdg-open > /dev/null; then
      log_info "Opening dashboard in browser..."
      xdg-open "http://localhost:$FRONTEND_PORT/competition" 2>/dev/null || true
    fi

    # Show live logs
    show_logs
    ;;
esac
