#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Competition Trading Bot — Start/Stop the engine and web dashboard
#
# Usage:
#   ./scripts/competition-start.sh                 start engine + web (full UI)
#   ./scripts/competition-start.sh --engine-only   engine only (no web)
#   ./scripts/competition-start.sh --web-only      web dashboard only
#   ./scripts/competition-start.sh --stop          stop all
#   ./scripts/competition-start.sh --status        show running processes
#
# Configuration:
#   Edit .env to set these variables (loaded automatically):
#   - COMPETITION_INSTRUMENTS   e.g., "EURUSD,GBPUSD,XAUUSD"
#   - COMPETITION_DRY_RUN       "1" for dry-run, "0" for live
#   - COMPETITION_NO_LLM        "1" to skip LLM (indicator-only mode)
#   - COMPETITION_ANALYSTS      which analysts to run
#   - LOG_DIR, TRADINGAGENTS_WEB_PORT, VITE_PORT
#   See .env file for full documentation
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load .env if it exists (so COMPETITION_* and other vars are available)
if [ -f "$PROJECT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

# Configuration
PID_FILE="$PROJECT_DIR/.competition.pids"
LOG_DIR="${LOG_DIR:-.logs}"
# Convert to absolute path so it works from any working directory
if [[ ! "$LOG_DIR" = /* ]]; then
  LOG_DIR="$PROJECT_DIR/$LOG_DIR"
fi
ENGINE_LOG="$LOG_DIR/competition-engine.log"
WEB_LOG="$LOG_DIR/competition-web.log"
FRONTEND_LOG="$LOG_DIR/competition-frontend.log"

API_PORT="${TRADINGAGENTS_WEB_PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"

INSTRUMENTS="${COMPETITION_INSTRUMENTS:-}"
DRY_RUN="${COMPETITION_DRY_RUN:-1}"
NO_LLM="${COMPETITION_NO_LLM:-}"

RUN_ENGINE=true
RUN_WEB=true
RUN_FRONTEND=true
OPEN_BROWSER=true

# -- Parse flags --------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --engine-only)   RUN_WEB=false; RUN_FRONTEND=false; OPEN_BROWSER=false ;;
    --web-only)      RUN_ENGINE=false; OPEN_BROWSER=false ;;
    --no-browser)    OPEN_BROWSER=false ;;
    --frontend-only) RUN_ENGINE=false; RUN_WEB=false ;;
    --status)
      if [ -f "$PID_FILE" ]; then
        source "$PID_FILE"
        echo "==> Competition services status:"
        [ -n "${ENGINE_PID:-}" ] && (kill -0 "$ENGINE_PID" 2>/dev/null && echo "  ✓ Engine (PID $ENGINE_PID)" || echo "  ✗ Engine (PID $ENGINE_PID — stopped)")
        [ -n "${WEB_PID:-}" ] && (kill -0 "$WEB_PID" 2>/dev/null && echo "  ✓ Web API (PID $WEB_PID on port $API_PORT)" || echo "  ✗ Web API (PID $WEB_PID — stopped)")
        [ -n "${FRONTEND_PID:-}" ] && (kill -0 "$FRONTEND_PID" 2>/dev/null && echo "  ✓ Frontend (PID $FRONTEND_PID on port $FRONTEND_PORT)" || echo "  ✗ Frontend (PID $FRONTEND_PID — stopped)")
      else
        echo "==> No competition services running"
      fi
      exit 0
      ;;
    --stop)
      echo "==> Stopping competition services ..."
      if [ -f "$PID_FILE" ]; then
        source "$PID_FILE"
        [ -n "${ENGINE_PID:-}" ] && kill "$ENGINE_PID" 2>/dev/null && echo "    Stopped engine (PID $ENGINE_PID)" || true
        [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null && echo "    Stopped web API (PID $WEB_PID)" || true
        [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "    Stopped frontend (PID $FRONTEND_PID)" || true
        rm "$PID_FILE"
        sleep 1
      fi
      # Fallback: kill by port
      lsof -ti:"$API_PORT" 2>/dev/null | xargs kill -9 2>/dev/null && echo "    Killed process on port $API_PORT" || true
      lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null && echo "    Killed process on port $FRONTEND_PORT" || true
      echo "Done."
      exit 0
      ;;
    --help)
      echo "Usage: $0 [--engine-only|--web-only|--frontend-only|--no-browser|--status|--stop|--help]"
      exit 0
      ;;
    *) echo "Unknown flag: $arg"; echo "Run '$0 --help' for usage"; exit 1 ;;
  esac
done

# -- Prerequisites ------------------------------------------------------------
command -v uv >/dev/null 2>&1 || { echo "❌ uv is required: pip install uv"; exit 1; }

mkdir -p "$LOG_DIR"

# -- Cleanup on exit ----------------------------------------------------------
cleanup() {
  echo ""
  echo "Shutting down ..."
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
    [ -n "${ENGINE_PID:-}" ] && echo "ENGINE_PID=$ENGINE_PID"
    [ -n "${WEB_PID:-}" ] && echo "WEB_PID=$WEB_PID"
    [ -n "${FRONTEND_PID:-}" ] && echo "FRONTEND_PID=$FRONTEND_PID"
  } > "$PID_FILE"
}

# -- Start competition engine -------------------------------------------------
if $RUN_ENGINE; then
  echo "==> Starting competition engine ..."

  # Build command
  ENGINE_CMD="uv run competition --mock"
  [ "$DRY_RUN" = "1" ] && ENGINE_CMD="$ENGINE_CMD --dry-run"
  [ -n "$NO_LLM" ] && ENGINE_CMD="$ENGINE_CMD --no-llm"
  [ -n "$INSTRUMENTS" ] && ENGINE_CMD="$ENGINE_CMD --instruments $INSTRUMENTS"

  # Engine runs separately; web-only will read persisted state

  eval "$ENGINE_CMD" > "$ENGINE_LOG" 2>&1 &
  ENGINE_PID=$!
  echo "    Engine running (PID $ENGINE_PID). Log: $ENGINE_LOG"

  # Give engine a moment to start
  sleep 1
fi

# -- Start web-only dashboard -------------------------------------------------
if $RUN_WEB; then
  echo "==> Starting web dashboard API ..."

  # Kill any existing process on the port
  if lsof -ti:"$API_PORT" >/dev/null 2>&1; then
    echo "    Port $API_PORT in use — stopping old process ..."
    lsof -ti:"$API_PORT" | xargs kill -9 2>/dev/null || true
    sleep 0.5
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
fi

# -- Start frontend dev server ------------------------------------------------
if $RUN_FRONTEND; then
  if $RUN_WEB; then
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

    # Wait for frontend to be ready
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
fi

save_pids

# -- Open browser -------------------------------------------------------------
if $OPEN_BROWSER && $RUN_FRONTEND; then
  URL="http://localhost:$FRONTEND_PORT/competition"
  echo ""
  echo "Opening $URL ..."
  open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || echo "  (Open manually: $URL)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Competition Trading is running:"
if $RUN_ENGINE; then
  echo "  Engine:   $([ "$DRY_RUN" = "1" ] && echo "DRY-RUN" || echo "LIVE")"
  [ -n "$INSTRUMENTS" ] && echo "           Instruments: $INSTRUMENTS"
  [ -n "$NO_LLM" ] && echo "           Indicator-only (no LLM)"
fi
if $RUN_WEB; then
  echo "  API:      http://localhost:$API_PORT"
fi
if $RUN_FRONTEND; then
  echo "  Frontend: http://localhost:$FRONTEND_PORT/competition"
fi
echo ""
echo "Usage:"
echo "  View logs:        tail -f $LOG_DIR/*.log"
echo "  Check status:     ./scripts/competition-start.sh --status"
echo "  Stop all:         ./scripts/competition-start.sh --stop"
echo "  Stop via Ctrl+C:  (press Ctrl+C below)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Wait for any process to exit
wait
