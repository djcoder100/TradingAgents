#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Competition Trading Bot — Distributed Mode (State Service + Engine + Web)
#
# This is the cloud-ready architecture:
# - State Service (port 9000) — central state store
# - Engine (separate process) — trading logic
# - Web API + Frontend — dashboard (reads from state service)
#
# All processes communicate via HTTP, so they can run on different machines.
#
# Usage:
#   ./scripts/competition-start-distributed.sh                 start everything
#   ./scripts/competition-start-distributed.sh --engine-only    engine only
#   ./scripts/competition-start-distributed.sh --service-only   state service only
#   ./scripts/competition-start-distributed.sh --stop           stop all
#   ./scripts/competition-start-distributed.sh --status         show status
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load .env if it exists
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

# Configuration
PID_FILE="$PROJECT_DIR/.competition-distributed.pids"
LOG_DIR="${LOG_DIR:-.logs}"
if [[ ! "$LOG_DIR" = /* ]]; then
  LOG_DIR="$PROJECT_DIR/$LOG_DIR"
fi
SERVICE_LOG="$LOG_DIR/competition-state-service.log"
ENGINE_LOG="$LOG_DIR/competition-engine.log"
WEB_LOG="$LOG_DIR/competition-web.log"
FRONTEND_LOG="$LOG_DIR/competition-frontend.log"

SERVICE_PORT="${COMPETITION_STATE_SERVICE_PORT:-9000}"
API_PORT="${TRADINGAGENTS_WEB_PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"
SERVICE_URL="http://localhost:$SERVICE_PORT"

INSTRUMENTS="${COMPETITION_INSTRUMENTS:-}"
DRY_RUN="${COMPETITION_DRY_RUN:-1}"
NO_LLM="${COMPETITION_NO_LLM:-}"

RUN_SERVICE=true
RUN_ENGINE=true
RUN_WEB=true
RUN_FRONTEND=true
OPEN_BROWSER=true

# -- Parse flags --------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --service-only)  RUN_ENGINE=false; RUN_WEB=false; RUN_FRONTEND=false; OPEN_BROWSER=false ;;
    --engine-only)   RUN_SERVICE=false; RUN_WEB=false; RUN_FRONTEND=false; OPEN_BROWSER=false ;;
    --web-only)      RUN_SERVICE=false; RUN_ENGINE=false; OPEN_BROWSER=false ;;
    --no-browser)    OPEN_BROWSER=false ;;
    --status)
      if [ -f "$PID_FILE" ]; then
        source "$PID_FILE"
        echo "==> Competition Distributed services status:"
        [ -n "${SERVICE_PID:-}" ] && (kill -0 "$SERVICE_PID" 2>/dev/null && echo "  ✓ State Service (PID $SERVICE_PID on port $SERVICE_PORT)" || echo "  ✗ State Service (PID $SERVICE_PID — stopped)")
        [ -n "${ENGINE_PID:-}" ] && (kill -0 "$ENGINE_PID" 2>/dev/null && echo "  ✓ Engine (PID $ENGINE_PID)" || echo "  ✗ Engine (PID $ENGINE_PID — stopped)")
        [ -n "${WEB_PID:-}" ] && (kill -0 "$WEB_PID" 2>/dev/null && echo "  ✓ Web API (PID $WEB_PID on port $API_PORT)" || echo "  ✗ Web API (PID $WEB_PID — stopped)")
        [ -n "${FRONTEND_PID:-}" ] && (kill -0 "$FRONTEND_PID" 2>/dev/null && echo "  ✓ Frontend (PID $FRONTEND_PID on port $FRONTEND_PORT)" || echo "  ✗ Frontend (PID $FRONTEND_PID — stopped)")
      else
        echo "==> No competition services running"
      fi
      exit 0
      ;;
    --stop)
      echo "==> Stopping competition distributed services ..."

      # First, try graceful shutdown with SIGTERM
      if [ -f "$PID_FILE" ]; then
        source "$PID_FILE"
        [ -n "${SERVICE_PID:-}" ] && kill -TERM "$SERVICE_PID" 2>/dev/null || true
        [ -n "${ENGINE_PID:-}" ] && kill -TERM "$ENGINE_PID" 2>/dev/null || true
        [ -n "${WEB_PID:-}" ] && kill -TERM "$WEB_PID" 2>/dev/null || true
        [ -n "${FRONTEND_PID:-}" ] && kill -TERM "$FRONTEND_PID" 2>/dev/null || true

        # Wait for graceful shutdown
        sleep 2

        # Force kill any remaining processes
        [ -n "${SERVICE_PID:-}" ] && kill -9 "$SERVICE_PID" 2>/dev/null && echo "    Force killed state service (PID $SERVICE_PID)" || echo "    State service stopped" && true
        [ -n "${ENGINE_PID:-}" ] && kill -9 "$ENGINE_PID" 2>/dev/null && echo "    Force killed engine (PID $ENGINE_PID)" || echo "    Engine stopped" && true
        [ -n "${WEB_PID:-}" ] && kill -9 "$WEB_PID" 2>/dev/null && echo "    Force killed web API (PID $WEB_PID)" || echo "    Web API stopped" && true
        [ -n "${FRONTEND_PID:-}" ] && kill -9 "$FRONTEND_PID" 2>/dev/null && echo "    Force killed frontend (PID $FRONTEND_PID)" || echo "    Frontend stopped" && true

        rm -f "$PID_FILE"
      fi

      # Kill any remaining processes on the ports
      echo "    Cleaning up ports..."
      lsof -ti:"$SERVICE_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
      lsof -ti:"$API_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
      lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true

      # Also kill any stale competition processes
      pkill -9 -f "competition --" 2>/dev/null || true
      pkill -9 -f "uvicorn" 2>/dev/null || true
      pkill -9 -f "vite" 2>/dev/null || true

      sleep 1
      echo "Done. All services stopped."
      exit 0
      ;;
    *) echo "Unknown flag: $arg"; echo "Usage: $0 [--service-only|--engine-only|--web-only|--no-browser|--status|--stop]"; exit 1 ;;
  esac
done

# -- Prerequisites ------------------------------------------------------------
command -v uv >/dev/null 2>&1 || { echo "❌ uv is required: pip install uv"; exit 1; }
mkdir -p "$LOG_DIR"

# -- Cleanup on exit ----------------------------------------------------------
cleanup() {
  echo ""
  echo "Shutting down ..."
  if [ -n "${SERVICE_PID:-}" ]; then kill "$SERVICE_PID" 2>/dev/null || true; fi
  if [ -n "${ENGINE_PID:-}" ]; then kill "$ENGINE_PID" 2>/dev/null || true; fi
  if [ -n "${WEB_PID:-}" ]; then kill "$WEB_PID" 2>/dev/null || true; fi
  if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  rm -f "$PID_FILE"
  wait 2>/dev/null || true
  echo "Done. Logs saved to $LOG_DIR/"
}
trap cleanup EXIT INT TERM

# -- Save PIDs ----------------------------------------------------------------
save_pids() {
  {
    [ -n "${SERVICE_PID:-}" ] && echo "SERVICE_PID=$SERVICE_PID"
    [ -n "${ENGINE_PID:-}" ] && echo "ENGINE_PID=$ENGINE_PID"
    [ -n "${WEB_PID:-}" ] && echo "WEB_PID=$WEB_PID"
    [ -n "${FRONTEND_PID:-}" ] && echo "FRONTEND_PID=$FRONTEND_PID"
  } > "$PID_FILE"
}

# -- Start state service ------------------------------------------------------
if $RUN_SERVICE; then
  echo "==> Starting state service on port $SERVICE_PORT ..."
  uv run uvicorn competition.state_service:app --host 0.0.0.0 --port "$SERVICE_PORT" > "$SERVICE_LOG" 2>&1 &
  SERVICE_PID=$!
  echo "    State service running (PID $SERVICE_PID). Log: $SERVICE_LOG"

  # Wait for service to be ready
  echo -n "    Waiting for state service to be ready..."
  for i in {1..30}; do
    if curl -s "http://localhost:$SERVICE_PORT/api/health" >/dev/null 2>&1; then
      echo " ✓"
      break
    fi
    echo -n "."
    sleep 0.5
  done
fi

# -- Start engine (with state service URL set) --------------------------------
if $RUN_ENGINE; then
  echo "==> Starting competition engine ..."

  ENGINE_CMD="uv run competition --mock"
  [ "$DRY_RUN" = "1" ] && ENGINE_CMD="$ENGINE_CMD --dry-run"
  [ -n "$NO_LLM" ] && ENGINE_CMD="$ENGINE_CMD --no-llm"
  [ -n "$INSTRUMENTS" ] && ENGINE_CMD="$ENGINE_CMD --instruments $INSTRUMENTS"

  # Set state service URL for engine to publish to
  if $RUN_SERVICE; then
    export COMPETITION_STATE_SERVICE_URL="$SERVICE_URL"
    echo "    Using state service at $SERVICE_URL"
  fi

  eval "$ENGINE_CMD" > "$ENGINE_LOG" 2>&1 &
  ENGINE_PID=$!
  echo "    Engine running (PID $ENGINE_PID). Log: $ENGINE_LOG"

  sleep 1
fi

# -- Start web + frontend -----------------------------------------------------
if $RUN_WEB; then
  echo "==> Starting web dashboard API ..."

  # Kill any existing process on the port
  if lsof -ti:"$API_PORT" >/dev/null 2>&1; then
    echo "    Port $API_PORT in use — stopping old process ..."
    lsof -ti:"$API_PORT" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi

  # Set state service URL for web to read from
  if $RUN_SERVICE; then
    export COMPETITION_STATE_SERVICE_URL="$SERVICE_URL"
  fi

  uv run competition --web-only > "$WEB_LOG" 2>&1 &
  WEB_PID=$!
  echo "    Web API running (PID $WEB_PID) on http://localhost:$API_PORT. Log: $WEB_LOG"

  # Wait for API to be ready
  echo -n "    Waiting for API to be ready..."
  for i in {1..30}; do
    if curl -s "http://localhost:$API_PORT/api/competition/state" >/dev/null 2>&1; then
      echo " ✓"
      break
    fi
    echo -n "."
    sleep 0.5
  done

  # Start frontend
  echo "==> Starting frontend dev server ..."

  if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    echo "    Installing frontend dependencies (one-time) ..."
    cd "$PROJECT_DIR/frontend" && npm install --silent && cd "$PROJECT_DIR"
  fi

  cd "$PROJECT_DIR/frontend"
  npx vite --port "$FRONTEND_PORT" --strictPort > "$FRONTEND_LOG" 2>&1 &
  FRONTEND_PID=$!
  cd "$PROJECT_DIR"
  echo "    Frontend running (PID $FRONTEND_PID) on http://localhost:$FRONTEND_PORT. Log: $FRONTEND_LOG"

  echo -n "    Waiting for frontend to be ready..."
  for i in {1..30}; do
    if curl -s "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
      echo " ✓"
      break
    fi
    echo -n "."
    sleep 0.5
  done
fi

save_pids

# -- Open browser if requested ------------------------------------------------
if $OPEN_BROWSER && $RUN_WEB; then
  URL="http://localhost:$FRONTEND_PORT/competition"
  echo ""
  echo "Opening $URL ..."
  open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || echo "  (Open manually: $URL)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Competition Trading (Distributed Mode) is running:"
if $RUN_SERVICE; then
  echo "  State Service: http://localhost:$SERVICE_PORT"
fi
if $RUN_ENGINE; then
  echo "  Engine:        $([ "$DRY_RUN" = "1" ] && echo "DRY-RUN" || echo "LIVE")"
fi
if $RUN_WEB; then
  echo "  Web API:       http://localhost:$API_PORT"
  echo "  Frontend:      http://localhost:$FRONTEND_PORT/competition"
fi
echo ""
echo "Architecture: State Service ← Engine, Web reads State Service"
echo "Deployment: Can run on separate machines with COMPETITION_STATE_SERVICE_URL"
echo ""
echo "Usage:"
echo "  View logs:        tail -f $LOG_DIR/*.log"
echo "  Check status:     ./scripts/competition-start-distributed.sh --status"
echo "  Stop all:         ./scripts/competition-start-distributed.sh --stop"
echo "  Stop via Ctrl+C:  (press Ctrl+C below)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Wait for any process to exit
wait
