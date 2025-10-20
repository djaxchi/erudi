#!/bin/bash

# Development start script for Erudi
# Starts both backend and frontend in development mode

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

# Function to cleanup background processes
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${BLUE}🔌 Stopping backend (PID: $BACKEND_PID)...${NC}"
        kill $BACKEND_PID
    fi
    
    # Kill any remaining backend processes
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

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

# Start backend
echo -e "${BLUE}🐍 Starting Python backend...${NC}"
cd "$PROJECT_ROOT/backend"
source venv/bin/activate

# Check if port 8000 is already in use
if lsof -i :8000 >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use. Killing existing processes...${NC}"
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    sleep 2
fi

# Start backend in background
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
echo -e "${BLUE}📝 Backend logs will appear below:${NC}"

# Wait a moment for backend to start
echo -e "${BLUE}⏳ Waiting for backend to be ready...${NC}"
sleep 3

# Check if backend is responding
for i in {1..10}; do
    if curl -s http://localhost:8000/main_window/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is responding!${NC}"
        break
    else
        if [ $i -eq 10 ]; then
            echo -e "${RED}❌ Backend failed to start after 10 seconds${NC}"
            exit 1
        fi
        echo -e "${YELLOW}⏳ Waiting for backend... (attempt $i/10)${NC}"
        sleep 1
    fi
done

# Start frontend
echo -e "${BLUE}⚛️  Starting Electron frontend...${NC}"
cd "$PROJECT_ROOT/frontend"

echo -e "${GREEN}🎉 Development environment is ready!${NC}"
echo -e "${BLUE}📝 Backend API: http://localhost:8000${NC}"
echo -e "${BLUE}📱 Electron app will open automatically${NC}"
echo -e "${YELLOW}💡 Press Ctrl+C to stop all services${NC}"

# Start frontend (this will block until the app is closed)
npm start

# This will be reached when npm start exits
echo -e "${BLUE}👋 Frontend closed${NC}"