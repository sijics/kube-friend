#!/usr/bin/env bash
# run.sh — start kubefriend natively (no Docker)
#
# Starts:
#   - Backend:  uvicorn on http://localhost:8000
#   - Frontend: vite dev server on http://localhost:5173
#
# PIDs are stored in .kubefriend/ so stop.sh can kill them cleanly.
# Logs go to .kubefriend/backend.log and .kubefriend/frontend.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$REPO_ROOT/.kubefriend"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"
BACKEND_LOG="$PID_DIR/backend.log"
FRONTEND_LOG="$PID_DIR/frontend.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $*"; }
info() { echo -e "${BLUE}→${RESET} $*"; }
warn() { echo -e "${YELLOW}⚠${RESET} $*"; }
die()  { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }

mkdir -p "$PID_DIR"

# ── Resolve uv — check common install locations ───────────────────────────────
UV=""
for candidate in \
  "$(command -v uv 2>/dev/null)" \
  "$HOME/.local/bin/uv" \
  "$HOME/.cargo/bin/uv" \
  "$HOME/.langflow/uv/uv" \
  "/opt/homebrew/bin/uv"; do
  if [[ -x "$candidate" ]]; then UV="$candidate"; break; fi
done

# ── Preflight checks ──────────────────────────────────────────────────────────

# Check .env exists
[[ ! -f "$REPO_ROOT/.env" ]] && die ".env not found. Run ./install.sh first."

# Check uv is available
[[ -z "$UV" ]] && die "uv not found. Run ./install.sh first."

# Check backend .venv exists
[[ ! -d "$REPO_ROOT/backend/.venv" ]] && die "Backend .venv not found. Run ./install.sh first."

# Check node_modules exists
[[ ! -d "$REPO_ROOT/frontend/node_modules" ]] && die "Frontend node_modules not found. Run ./install.sh first."

# Check if already running
if [[ -f "$BACKEND_PID" ]] && kill -0 "$(cat "$BACKEND_PID")" 2>/dev/null; then
  warn "kubefriend is already running (backend PID $(cat "$BACKEND_PID"))"
  warn "Run ./stop.sh first, or ./kubefriend stop"
  exit 0
fi

echo ""
echo -e "${BOLD}⎈  Starting kubefriend${RESET}"
echo "────────────────────────────────────"

# Show current kubectl context
CONTEXT=$(kubectl config current-context 2>/dev/null || echo "none")
SERVER=$(kubectl config view --minify --output jsonpath='{.clusters[0].cluster.server}' 2>/dev/null || echo "unknown")
echo -e "  Cluster context : ${BOLD}$CONTEXT${RESET}"
echo -e "  API server      : $SERVER"
echo ""

# ── Start backend ─────────────────────────────────────────────────────────────
info "Starting backend (FastAPI on :8000)..."

cd "$REPO_ROOT/backend"

# Export .env variables for the backend process
set -a; source "$REPO_ROOT/.env"; set +a

# Start uvicorn using the venv's Python
"$REPO_ROOT/backend/.venv/bin/uvicorn" \
  app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  >> "$BACKEND_LOG" 2>&1 &

echo $! > "$BACKEND_PID"
ok "Backend started (PID $(cat "$BACKEND_PID")) → logs: .kubefriend/backend.log"

# Wait for backend to be ready
info "Waiting for backend to be ready..."
for i in {1..20}; do
  if curl -sf http://localhost:8000/healthz &>/dev/null; then
    ok "Backend is ready"
    break
  fi
  sleep 0.5
  if [[ $i -eq 20 ]]; then
    warn "Backend didn't respond in 10s — check logs: tail -f .kubefriend/backend.log"
  fi
done

# ── Start frontend ────────────────────────────────────────────────────────────
info "Starting frontend (Vite dev server on :5173)..."

cd "$REPO_ROOT/frontend"
npm run dev \
  >> "$FRONTEND_LOG" 2>&1 &

echo $! > "$FRONTEND_PID"
ok "Frontend started (PID $(cat "$FRONTEND_PID")) → logs: .kubefriend/frontend.log"

# Wait for frontend to be ready
info "Waiting for frontend to be ready..."
sleep 2
for i in {1..15}; do
  if curl -sf http://localhost:5173 &>/dev/null; then
    ok "Frontend is ready"
    break
  fi
  sleep 0.5
done

# ── Open browser ──────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ kubefriend is running!${RESET}"
echo ""
echo -e "  ${BOLD}http://localhost:5173${RESET}   ← open this in your browser"
echo ""
echo "  Commands:"
echo "    ./kubefriend status           — check if running"
echo "    ./kubefriend logs             — tail live logs"
echo "    ./kubefriend switch <context> — switch cluster"
echo "    ./kubefriend stop             — stop everything"
echo ""

# Auto-open browser (macOS)
open "http://localhost:5173" 2>/dev/null || true
