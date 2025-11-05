#!/bin/bash

# Build script for Erudi - Electron app with embedded Python backend
# This script automates the complete build process
#
# Usage:
#   ./build-erudi.sh                 # Full build (backend + frontend)
#   ./build-erudi.sh --skip-backend  # Skip backend rebuild

set -e  # Exit on any error

# Parse command line arguments
SKIP_BACKEND=false
for arg in "$@"; do
  case $arg in
    --skip-backend)
      SKIP_BACKEND=true
      shift
      ;;
    *)
      echo "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Erudi build process...${NC}"

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Point to the actual erudi project location
PROJECT_ROOT="/Users/djadja/Code/erudi"

echo -e "${YELLOW}📁 Project root: $PROJECT_ROOT${NC}"

# Load notarization credentials if available
if [ -f "$PROJECT_ROOT/.env.notarize" ]; then
    echo -e "${GREEN}🔐 Loading notarization credentials from .env.notarize${NC}"
    source "$PROJECT_ROOT/.env.notarize"
    
    # Verify credentials are loaded
    if [ -n "$APPLE_ID" ] && [ -n "$APPLE_TEAM_ID" ] && [ -n "$APPLE_SIGNING_IDENTITY" ]; then
        echo -e "${GREEN}✅ Notarization credentials loaded successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Some notarization credentials are missing${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No .env.notarize file found - build will not be notarized${NC}"
fi

# Step 1: Build backend with PyInstaller (unless skipped)
if [ "$SKIP_BACKEND" = true ]; then
    echo -e "${YELLOW}⏭️  Skipping backend rebuild (--skip-backend flag set)${NC}"
    
    # Verify backend already exists
    if [ ! -f "$PROJECT_ROOT/backend/dist/backend/backend" ]; then
        echo -e "${RED}❌ Backend executable not found at $PROJECT_ROOT/backend/dist/backend/backend${NC}"
        echo -e "${RED}   Run without --skip-backend to rebuild it first${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Using existing backend build${NC}"
else
    echo -e "${BLUE}🔄 Step 1: Building backend with PyInstaller...${NC}"
    cd "$PROJECT_ROOT/backend"

    # Clean up old database before building
    echo -e "${BLUE}🧹 Cleaning up old database...${NC}"
    if [ -f "data/erudi.db" ]; then
        echo -e "${YELLOW}🗑️  Removing old erudi.db${NC}"
        rm -f data/erudi.db
        echo -e "${GREEN}✅ Old database removed${NC}"
    else
        echo -e "${YELLOW}ℹ️  No existing database found${NC}"
    fi

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo -e "${RED}❌ Virtual environment not found. Creating one...${NC}"
        python -m venv venv
        source venv/bin/activate
        echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
        pip install --upgrade pip
        pip install -r requirements.txt
    else
        echo -e "${BLUE}♻️  Virtual environment found. Refreshing dependencies...${NC}"
        source venv/bin/activate
        echo -e "${BLUE}📦 Updating Python dependencies...${NC}"
        pip install --upgrade pip
        pip install --upgrade -r requirements.txt
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
fi

# Step 2: Install frontend dependencies if needed
echo -e "${BLUE}🔍 Step 2: Checking frontend dependencies...${NC}"
cd "$PROJECT_ROOT/frontend"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📥 Installing frontend dependencies...${NC}"
    npm install
fi

# Step 3: Build Electron app
echo -e "${BLUE}⚡ Step 3: Building Electron app...${NC}"

# Clean old builds
if [ -d "out" ]; then
    echo -e "${YELLOW}🗑️  Cleaning old builds...${NC}"
    rm -rf out/
fi

# Build the app
npm run make

# Step 4: Verify build results
echo -e "${BLUE}🔍 Step 4: Verifying build results...${NC}"

# Check for DMG file (preferred for macOS)
DMG_PATH="$PROJECT_ROOT/frontend/out/make/Erudi-Installer.dmg"
ZIP_PATH="$PROJECT_ROOT/frontend/out/make/zip/darwin/arm64/erudi-darwin-arm64-1.0.0.zip"

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
elif [ -f "$ZIP_PATH" ]; then
    echo -e "${GREEN}✅ Build completed successfully!${NC}"
    echo -e "${GREEN}📦 ZIP package available at:${NC}"
    echo -e "${GREEN}   $ZIP_PATH${NC}"
    
    # Get file size
    ZIP_SIZE=$(du -h "$ZIP_PATH" | cut -f1)
    echo -e "${BLUE}📊 Package size: $ZIP_SIZE${NC}"
    
    # Show the containing folder
    echo -e "${YELLOW}💡 Opening build folder...${NC}"
    open "$PROJECT_ROOT/frontend/out/make/zip/darwin/arm64/"
else
    echo -e "${RED}❌ Build failed! Neither DMG nor ZIP found.${NC}"
    echo -e "${RED}   Expected DMG: $DMG_PATH${NC}"
    echo -e "${RED}   Expected ZIP: $ZIP_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 Erudi build process completed successfully!${NC}"