#!/usr/bin/env bash
# install.sh — one-time setup for kubefriend on macOS
#
# What this does:
#   1. Checks prerequisites (Python 3.12+, Node, uv)
#   2. Installs uv if missing
#   3. Installs Node via nvm or Homebrew if missing
#   4. Creates backend/.venv and syncs Python dependencies
#   5. Installs frontend Node dependencies
#   6. Creates .env from .env.example if not already present
#   7. Prints next steps
#
# Usage:
#   chmod +x install.sh && ./install.sh

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $*"; }
info() { echo -e "${BLUE}→${RESET} $*"; }
warn() { echo -e "${YELLOW}⚠${RESET} $*"; }
die()  { echo -e "${RED}✗ ERROR:${RESET} $*" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${BOLD}⎈  kubefriend — install${RESET}"
echo "────────────────────────────────────"
echo ""

# ── 1. Python 3.12+ ───────────────────────────────────────────────────────────
info "Checking Python..."
PYTHON=$(command -v python3 || command -v python || true)
[[ -z "$PYTHON" ]] && die "Python 3.12+ is required. Install from https://python.org"

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
[[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 12) ]] && \
  die "Python 3.12+ required, found $PY_VER. Install from https://python.org"
ok "Python $PY_VER"

# ── 2. uv ─────────────────────────────────────────────────────────────────────
info "Checking uv (Python package manager)..."
if ! command -v uv &>/dev/null; then
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Add uv to current shell session
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi
UV=$(command -v uv)
ok "uv $(uv --version 2>/dev/null | head -1)"

# ── 3. Node.js 18+ ────────────────────────────────────────────────────────────
info "Checking Node.js..."
if ! command -v node &>/dev/null; then
  warn "Node.js not found."
  if command -v brew &>/dev/null; then
    info "Installing Node.js via Homebrew..."
    brew install node
  elif command -v nvm &>/dev/null; then
    info "Installing Node.js via nvm..."
    nvm install --lts
    nvm use --lts
  else
    die "Node.js is required.\n  Install via Homebrew: brew install node\n  Or from: https://nodejs.org"
  fi
fi
NODE_VER=$(node --version)
ok "Node.js $NODE_VER"

# ── 4. Backend Python dependencies ────────────────────────────────────────────
info "Installing backend Python dependencies..."
cd "$REPO_ROOT/backend"
$UV sync --frozen 2>&1 | tail -3
ok "Backend dependencies installed (.venv created)"

# ── 5. Frontend Node dependencies ─────────────────────────────────────────────
info "Installing frontend Node dependencies..."
cd "$REPO_ROOT/frontend"
npm install --silent
ok "Frontend dependencies installed"

# ── 6. .env setup ─────────────────────────────────────────────────────────────
cd "$REPO_ROOT"
if [[ ! -f ".env" ]]; then
  info "Creating .env from .env.example..."
  cp .env.example .env
  warn ".env created — open it and fill in your OPENAI_API_KEY or watsonx credentials"
else
  ok ".env already exists"
fi

# ── 7. Make scripts executable ────────────────────────────────────────────────
chmod +x "$REPO_ROOT/run.sh" "$REPO_ROOT/stop.sh" "$REPO_ROOT/kubefriend" 2>/dev/null || true

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ kubefriend installed successfully!${RESET}"
echo ""
echo "  Next steps:"
echo "  1. Edit .env and add your API key:"
echo "     ${BOLD}nano .env${RESET}"
echo ""
echo "  2. Start kubefriend:"
echo "     ${BOLD}./kubefriend start${RESET}"
echo "     or: ${BOLD}make run${RESET}"
echo ""
echo "  3. Switch Kubernetes context anytime:"
echo "     ${BOLD}./kubefriend switch <context-name>${RESET}"
echo "     or: ${BOLD}kubectl config use-context <context-name>${RESET}"
echo ""
echo "  Available contexts:"
kubectl config get-contexts --no-headers 2>/dev/null | awk '{print "     " $2}' | head -10 || true
echo ""
