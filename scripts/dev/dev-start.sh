#!/bin/bash

# Development start script for Erudi
# Starts backend and frontend in separate Terminal windows on macOS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🚀 Starting Erudi development environment...${NC}"
echo -e "${YELLOW}📁 Project root: $PROJECT_ROOT${NC}"

# Check dependencies
echo -e "${BLUE}🔍 Checking dependencies...${NC}"

# Check if Python backend virtual environment exists
if [ ! -d "$PROJECT_ROOT/backend/venv" ]; then
    echo -e "${YELLOW}⚠️  Backend virtual environment not found. Creating...${NC}"
    cd "$PROJECT_ROOT/backend"
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd "$PROJECT_ROOT"
fi

# Check if frontend dependencies are installed
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠️  Frontend dependencies not found. Installing...${NC}"
    cd "$PROJECT_ROOT/frontend"
    npm install
    cd "$PROJECT_ROOT"
fi

# Kill any existing backend process on port 8000
if lsof -i :8000 >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use. Killing existing processes...${NC}"
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    sleep 2
fi

# Create temporary script for backend
BACKEND_SCRIPT="/tmp/erudi-backend-dev.sh"
cat > "$BACKEND_SCRIPT" << BACKEND_EOF
#!/bin/bash
cd "$PROJECT_ROOT/backend"
source venv/bin/activate
echo "Starting backend on port 8000..."
uvicorn app.main:app --reload --port 8000
BACKEND_EOF
chmod +x "$BACKEND_SCRIPT"

# Create temporary script for frontend
FRONTEND_SCRIPT="/tmp/erudi-frontend-dev.sh"
cat > "$FRONTEND_SCRIPT" << FRONTEND_EOF
#!/bin/bash
cd "$PROJECT_ROOT/frontend"
echo "Starting frontend..."
npm start
FRONTEND_EOF
chmod +x "$FRONTEND_SCRIPT"

echo -e "${GREEN}🎉 Development environment ready!${NC}"
echo -e "${BLUE}📝 Opening two Terminal windows:${NC}"
echo -e "${BLUE}  1️⃣  Backend terminal (port 8000)${NC}"
echo -e "${BLUE}  2️⃣  Frontend terminal (Electron app)${NC}"
echo ""

# Open backend in new Terminal window
osascript -e "tell application \"Terminal\" to do script \"$BACKEND_SCRIPT\""

# Wait a moment for backend to start
sleep 2

# Open frontend in new Terminal window
osascript -e "tell application \"Terminal\" to do script \"$FRONTEND_SCRIPT\""

echo -e "${GREEN}✅ Both terminals opened!${NC}"
echo -e "${YELLOW}💡 Close either terminal to stop that service${NC}"
echo -e "${YELLOW}💡 Close both to shut down the dev environment${NC}"

echo -e "${GREEN}🎉 Development environment ready!${NC}"
echo -e "${BLUE}📝 Opening two Terminal windows:${NC}"
echo -e "${BLUE}  1️⃣  Backend terminal (port 8000)${NC}"
echo -e "${BLUE}  2️⃣  Frontend terminal (Electron app)${NC}"
echo ""

# Open backend in new Terminal window
open -a Terminal "$BACKEND_SCRIPT" "$PROJECT_ROOT"

# Wait a moment for backend to start
sleep 2

# Open frontend in new Terminal window
open -a Terminal "$FRONTEND_SCRIPT" "$PROJECT_ROOT"

echo -e "${GREEN}✅ Both terminals opened!${NC}"
echo -e "${YELLOW}� Close either terminal to stop that service${NC}"
echo -e "${YELLOW}💡 Close both to shut down the dev environment${NC}"