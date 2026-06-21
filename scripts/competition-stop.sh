#!/usr/bin/env bash
# Stop all competition services immediately and forcefully
set -euo pipefail

echo "==> Killing all competition services..."

# Kill by process pattern (most reliable)
pkill -9 -f "competition --" 2>/dev/null || echo "  No competition processes found"
pkill -9 -f "uvicorn competition.state_service" 2>/dev/null || echo "  No state service found"
pkill -9 -f "competition --web-only" 2>/dev/null || echo "  No web service found"
pkill -9 -f "vite" 2>/dev/null || echo "  No vite found"

# Kill by port (fallback)
lsof -ti:9000 2>/dev/null | xargs kill -9 2>/dev/null || echo "  Port 9000 cleared"
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || echo "  Port 8000 cleared"
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || echo "  Port 5173 cleared"

# Clean up PID files
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
rm -f "$PROJECT_DIR/.competition.pids" "$PROJECT_DIR/.competition-distributed.pids"

sleep 1
echo "Done. All competition services stopped."
