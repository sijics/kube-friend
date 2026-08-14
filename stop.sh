#!/usr/bin/env bash
# stop.sh — stop kubefriend backend and frontend processes

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$REPO_ROOT/.kubefriend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}✓${RESET} $*"; }
info() { echo -e "${BLUE}→${RESET} $*"; }
warn() { echo -e "${YELLOW}⚠${RESET} $*"; }

stopped=0

stop_pid() {
  local name=$1 pidfile=$2
  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      info "Stopping $name (PID $pid)..."
      kill "$pid" 2>/dev/null || true
      # Wait up to 3s for clean exit
      for _ in {1..6}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      kill -9 "$pid" 2>/dev/null || true
      ok "$name stopped"
      stopped=$((stopped + 1))
    else
      warn "$name was not running (stale PID file)"
    fi
    rm -f "$pidfile"
  else
    warn "No PID file for $name — may not be running"
  fi
}

echo ""
echo "⎈  Stopping kubefriend..."
echo "────────────────────────────────────"

stop_pid "Backend"  "$PID_DIR/backend.pid"
stop_pid "Frontend" "$PID_DIR/frontend.pid"

# Also kill any stray uvicorn/vite processes on those ports (safety net)
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true

echo ""
if [[ $stopped -gt 0 ]]; then
  echo -e "${GREEN}✓ kubefriend stopped.${RESET}"
else
  echo -e "${GREEN}✓ Nothing was running.${RESET}"
fi
echo ""
