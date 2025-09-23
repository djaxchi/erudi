#!/bin/bash

# Build script for Erudi - Electron app with embedded Python backend
# This script automates the complete build process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Erudi build process...${NC}"

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}📁 Project root: $PROJECT_ROOT${NC}"

# Step 1: Build backend with PyInstaller
echo -e "${BLUE}🔄 Step 1: Building backend with PyInstaller...${NC}"
cd "$PROJECT_ROOT/backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Creating one...${NC}"
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo -e "${YELLOW}⚠️  PyInstaller not found. Installing...${NC}"
    pip install pyinstaller
fi

# Build the backend executable
echo -e "${BLUE}🔨 Building backend executable...${NC}"
pyinstaller backend.spec

# Check if build was successful
if [ ! -f "dist/backend/backend" ]; then
    echo -e "${RED}❌ Backend build failed! dist/backend/backend not found.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backend build successful!${NC}"

# Step 2: Copy backend to frontend
echo -e "${BLUE}📦 Step 2: Copying backend to frontend...${NC}"
cd "$PROJECT_ROOT/frontend"

# Remove old backend if it exists
if [ -d "backend" ]; then
    echo -e "${YELLOW}🗑️  Removing old backend...${NC}"
    rm -rf backend/
fi

# Copy new backend
echo -e "${BLUE}📋 Copying new backend build...${NC}"
cp -r ../backend/dist/backend ./backend

# Verify copy was successful
if [ ! -f "backend/backend" ]; then
    echo -e "${RED}❌ Backend copy failed! backend/backend not found.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backend copied successfully!${NC}"

# Step 3: Install frontend dependencies if needed
echo -e "${BLUE}🔍 Step 3: Checking frontend dependencies...${NC}"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📥 Installing frontend dependencies...${NC}"
    npm install
fi

# Step 4: Build Electron app
echo -e "${BLUE}⚡ Step 4: Building Electron app...${NC}"

# Clean old builds
if [ -d "out" ]; then
    echo -e "${YELLOW}🗑️  Cleaning old builds...${NC}"
    rm -rf out/
fi

# Build the app
npm run make

# Step 5: Verify build results
echo -e "${BLUE}🔍 Step 5: Verifying build results...${NC}"

DMG_PATH="$PROJECT_ROOT/frontend/out/make/Erudi-Installer.dmg"
if [ -f "$DMG_PATH" ]; then
    echo -e "${GREEN}✅ Build completed successfully!${NC}"
    echo -e "${GREEN}📦 DMG installer available at:${NC}"
    echo -e "${GREEN}   $DMG_PATH${NC}"
    
    # Get file size
    DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)
    echo -e "${BLUE}📊 DMG size: $DMG_SIZE${NC}"
    
    # Ask if user wants to open the DMG
    echo -e "${YELLOW}❓ Do you want to open the DMG installer? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        open "$DMG_PATH"
    fi
else
    echo -e "${RED}❌ Build failed! DMG not found at expected location.${NC}"
    echo -e "${RED}   Expected: $DMG_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 Erudi build process completed successfully!${NC}"