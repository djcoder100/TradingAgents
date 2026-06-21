#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BRV Trading — start / stop the API backend and React frontend.
#
# Usage:
#   ./scripts/start.sh                 start both, open browser
#   ./scripts/start.sh --no-browser    start both, don't open browser
#   ./scripts/start.sh --api-only      backend only
#   ./scripts/start.sh --web-only      frontend only
#   ./scripts/start.sh --stop          stop all running services
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

API_PORT="${TRADINGAGENTS_WEB_PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"
OPEN_BROWSER=true
RUN_API=true
RUN_WEB=true

# -- Parse flags --------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --no-browser) OPEN_BROWSER=false ;;
    --api-only)   RUN_WEB=false    ;;
    --web-only)   RUN_API=false    ;;
    --stop)
      echo "==> Stopping all BRV Trading services ..."
      lsof -ti:"$API_PORT" 2>/dev/null | xargs kill -9 2>/dev/null && echo "    Stopped API backend on port $API_PORT" || echo "    No API backend running on port $API_PORT"
      lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null && echo "    Stopped frontend on port $FRONTEND_PORT" || echo "    No frontend running on port $FRONTEND_PORT"
      echo "Done."
      exit 0
      ;;
    *) echo "Unknown flag: $arg"; echo "Usage: $0 [--no-browser|--api-only|--web-only|--stop]"; exit 1 ;;
  esac
done

# -- Prerequisites ------------------------------------------------------------
command -v uv >/dev/null 2>&1 || { echo "uv is required: pip install uv"; exit 1; }

if $RUN_WEB && [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
  echo "==> Installing frontend dependencies (one-time) ..."
  cd "$PROJECT_DIR/frontend" && npm install --silent && cd "$PROJECT_DIR"
fi

# -- Cleanup on exit ----------------------------------------------------------
cleanup() {
  echo ""
  echo "Shutting down ..."
  if [ -n "${API_PID:-}" ]; then kill "$API_PID" 2>/dev/null || true; fi
  if [ -n "${WEB_PID:-}" ]; then kill "$WEB_PID" 2>/dev/null || true; fi
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# -- Start API backend --------------------------------------------------------
if $RUN_API; then
  # Check for port conflict
  if lsof -ti:"$API_PORT" >/dev/null 2>&1; then
    echo "==> Port ${API_PORT} is in use — stopping the old process ..."
    lsof -ti:"$API_PORT" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi

  echo "==> Starting API backend on http://localhost:${API_PORT} ..."
  PYTHONPATH="$PROJECT_DIR" uv run uvicorn web.main:app \
    --host 0.0.0.0 --port "$API_PORT" \
    --log-level info &
  API_PID=$!

  # Wait until the API is ready
  for _ in $(seq 1 30); do
    if curl -s "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
      echo "    API ready."
      break
    fi
    sleep 0.5
  done
fi

# -- Start frontend dev server ------------------------------------------------
if $RUN_WEB; then
  echo "==> Starting frontend on http://localhost:${FRONTEND_PORT} ..."
  cd "$PROJECT_DIR/frontend"
  npx vite --port "$FRONTEND_PORT" --strictPort &
  WEB_PID=$!
  cd "$PROJECT_DIR"

  # Wait until the frontend is serving
  for _ in $(seq 1 30); do
    if curl -s "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
      echo "    Frontend ready."
      break
    fi
    sleep 0.5
  done
fi

# -- Open browser -------------------------------------------------------------
if $OPEN_BROWSER && $RUN_WEB; then
  URL="http://localhost:${FRONTEND_PORT}"
  echo ""
  echo "Opening $URL ..."
  open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || true
fi

echo ""
echo "BRV Trading is running."
echo "  API:      http://localhost:${API_PORT}"
echo "  Frontend: http://localhost:${FRONTEND_PORT}"
echo ""
echo "Press Ctrl+C to stop, or run './scripts/start.sh --stop'"

# Wait for either process to exit
wait
