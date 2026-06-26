#!/bin/bash
# Simple startup script — starts all services in background
# Usage: ./scripts/start.sh [--stop]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load .env
if [ -f ".env" ]; then
  set -a
  source ".env"
  set +a
fi

# Configuration
PID_FILE="$PROJECT_DIR/.trading-pids"
LOG_DIR="${LOG_DIR:-.logs}"
mkdir -p "$LOG_DIR"

SERVICE_PORT="${COMPETITION_STATE_SERVICE_PORT:-9000}"
API_PORT="${TRADINGAGENTS_WEB_PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"

SERVICE_LOG="$LOG_DIR/state-service.log"
ENGINE_LOG="$LOG_DIR/engine.log"
WEB_LOG="$LOG_DIR/web-api.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

INSTRUMENTS="${COMPETITION_INSTRUMENTS:-XAUUSD,EURUSD,GBPUSD}"

# Handle --stop flag
if [ "${1:-}" = "--stop" ]; then
  echo "Stopping all services..."
  if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
      kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  pkill -f "uvicorn.*web.main" 2>/dev/null || true
  pkill -f "npm run dev" 2>/dev/null || true
  echo "✓ All services stopped"
  exit 0
fi

# Stop existing processes
echo "Stopping any existing services..."
if [ -f "$PID_FILE" ]; then
  while IFS= read -r pid; do
    kill "$pid" 2>/dev/null || true
  done < "$PID_FILE"
fi
pkill -f "uvicorn.*web.main" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
sleep 1

# Clear PID file and logs
rm -f "$PID_FILE"
rm -f "$SERVICE_LOG" "$WEB_LOG" "$ENGINE_LOG" "$FRONTEND_LOG"

# Start services
echo "Starting State Service..."
uv run python3 -m competition.state_service > "$SERVICE_LOG" 2>&1 &
echo $! >> "$PID_FILE"
sleep 2

echo "Starting Web API..."
uv run uvicorn web.main:app --host 0.0.0.0 --port "$API_PORT" > "$WEB_LOG" 2>&1 &
echo $! >> "$PID_FILE"
sleep 2

echo "Starting Engine..."
uv run competition --mock --dry-run --instruments "$INSTRUMENTS" --log-level INFO > "$ENGINE_LOG" 2>&1 &
echo $! >> "$PID_FILE"
sleep 2

echo "Starting Frontend..."
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
  echo "  Installing frontend dependencies (one-time)..."
  (cd "$PROJECT_DIR/frontend" && npm install --silent)
fi
# Start frontend - use absolute path for log file
npm --prefix "$PROJECT_DIR/frontend" run dev > "$PROJECT_DIR/$LOG_DIR/frontend.log" 2>&1 &
echo $! >> "$PID_FILE"
sleep 5

# Show status
echo ""
echo "✓ All services started!"
echo ""
echo "Dashboard:  http://localhost:$FRONTEND_PORT/competition"
echo "API:        http://localhost:$API_PORT/api"
echo "State:      http://localhost:$SERVICE_PORT/api/competition/state"
echo ""
echo "Log files in: $LOG_DIR/"
echo ""
echo "View logs:"
echo "  tail -f $SERVICE_LOG"
echo "  tail -f $WEB_LOG"
echo "  tail -f $ENGINE_LOG"
echo "  tail -f $FRONTEND_LOG"
echo ""
echo "Or all at once:"
echo "  tail -f $LOG_DIR/*.log"
echo ""
echo "To stop:"
echo "  ./scripts/start.sh --stop"
echo ""
