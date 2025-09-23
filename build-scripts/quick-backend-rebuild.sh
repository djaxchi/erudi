#!/bin/bash

# Quick rebuild script for when you've only changed the backend code
# This script rebuilds just the backend and copies it to frontend

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

echo -e "${BLUE}🔄 Quick backend rebuild...${NC}"

# Step 1: Build backend
echo -e "${BLUE}🐍 Building backend...${NC}"
cd "$PROJECT_ROOT/backend"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo -e "${RED}❌ Virtual environment not found! Run full build first.${NC}"
    exit 1
fi

# Build with PyInstaller
pyinstaller backend.spec

# Step 2: Copy to frontend
echo -e "${BLUE}📦 Updating frontend backend...${NC}"
cd "$PROJECT_ROOT/frontend"

# Remove old backend
rm -rf backend/

# Copy new build
cp -r ../backend/dist/backend ./backend

echo -e "${GREEN}✅ Backend updated successfully!${NC}"
echo -e "${YELLOW}💡 Run 'npm run make' in frontend/ to rebuild the Electron app${NC}"