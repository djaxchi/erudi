#!/usr/bin/env bash
# dev-start.sh
# Starts the Erudi backend + Electron frontend in separate Terminal windows.
#
# Usage (from repo root):
#   bash scripts/dev/dev-start.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-27182}"

echo -e "${BLUE}Starting Erudi dev environment...${NC}"
echo -e "${YELLOW}Project root: $PROJECT_ROOT${NC}"
echo -e "${YELLOW}Backend port: $BACKEND_PORT${NC}"

# Prefer .venv over venv if both exist
if [ -f "$PROJECT_ROOT/backend/.venv/bin/activate" ]; then
    VENV_ACTIVATE="$PROJECT_ROOT/backend/.venv/bin/activate"
elif [ -f "$PROJECT_ROOT/backend/venv/bin/activate" ]; then
    VENV_ACTIVATE="$PROJECT_ROOT/backend/venv/bin/activate"
else
    echo "No virtual environment found. Run: bash scripts/dev/backend/setup-mac-silicon.sh"
    exit 1
fi

# Frontend deps
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd "$PROJECT_ROOT/frontend" && npm install
fi

# Kill anything already on the port
if lsof -ti ":$BACKEND_PORT" >/dev/null 2>&1; then
    echo -e "${YELLOW}Killing process on port $BACKEND_PORT...${NC}"
    lsof -ti ":$BACKEND_PORT" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Backend script
BACKEND_SCRIPT="/tmp/erudi-backend-dev.sh"
cat > "$BACKEND_SCRIPT" << BACKEND_EOF
#!/usr/bin/env bash
cd "$PROJECT_ROOT/backend"
source "$VENV_ACTIVATE"
echo "Backend starting on port $BACKEND_PORT..."
PYTHONPATH=. uvicorn src.main:app --reload --port $BACKEND_PORT
BACKEND_EOF
chmod +x "$BACKEND_SCRIPT"

# Frontend script
FRONTEND_SCRIPT="/tmp/erudi-frontend-dev.sh"
cat > "$FRONTEND_SCRIPT" << FRONTEND_EOF
#!/usr/bin/env bash
cd "$PROJECT_ROOT/frontend"
BACKEND_PORT=$BACKEND_PORT npm start
FRONTEND_EOF
chmod +x "$FRONTEND_SCRIPT"

# Open terminals
osascript -e "tell application \"Terminal\" to do script \"$BACKEND_SCRIPT\""
sleep 3
osascript -e "tell application \"Terminal\" to do script \"$FRONTEND_SCRIPT\""

echo -e "${GREEN}Done — two Terminal windows opened.${NC}"
