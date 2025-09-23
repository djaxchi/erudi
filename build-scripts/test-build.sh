#!/bin/bash

# Test script to verify the Erudi build
# This script performs various checks to ensure the build is working correctly

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

echo -e "${BLUE}🧪 Testing Erudi build...${NC}"

# Test 1: Check if backend executable exists
echo -e "${BLUE}🔍 Test 1: Backend executable exists${NC}"
BACKEND_EXEC="$PROJECT_ROOT/frontend/backend/backend"
if [ -f "$BACKEND_EXEC" ]; then
    echo -e "${GREEN}✅ Backend executable found${NC}"
    
    # Check if executable is ARM64 (for Apple Silicon)
    if file "$BACKEND_EXEC" | grep -q "arm64"; then
        echo -e "${GREEN}✅ Backend is ARM64 compatible${NC}"
    else
        echo -e "${YELLOW}⚠️  Backend is not ARM64 (may not work on Apple Silicon)${NC}"
    fi
else
    echo -e "${RED}❌ Backend executable not found at $BACKEND_EXEC${NC}"
fi

# Test 2: Check if _internal directory exists
echo -e "${BLUE}🔍 Test 2: Backend dependencies${NC}"
INTERNAL_DIR="$PROJECT_ROOT/frontend/backend/_internal"
if [ -d "$INTERNAL_DIR" ]; then
    echo -e "${GREEN}✅ Backend _internal directory found${NC}"
    DEP_COUNT=$(ls -1 "$INTERNAL_DIR" | wc -l)
    echo -e "${BLUE}📊 Dependencies count: $DEP_COUNT${NC}"
else
    echo -e "${RED}❌ Backend _internal directory not found${NC}"
fi

# Test 3: Check frontend package.json
echo -e "${BLUE}🔍 Test 3: Frontend configuration${NC}"
PACKAGE_JSON="$PROJECT_ROOT/frontend/package.json"
if [ -f "$PACKAGE_JSON" ]; then
    echo -e "${GREEN}✅ Frontend package.json found${NC}"
    
    # Check if electron-forge is configured
    if grep -q "electron-forge" "$PACKAGE_JSON"; then
        echo -e "${GREEN}✅ Electron Forge is configured${NC}"
    else
        echo -e "${RED}❌ Electron Forge not found in package.json${NC}"
    fi
else
    echo -e "${RED}❌ Frontend package.json not found${NC}"
fi

# Test 4: Check forge.config.js
echo -e "${BLUE}🔍 Test 4: Forge configuration${NC}"
FORGE_CONFIG="$PROJECT_ROOT/frontend/forge.config.js"
if [ -f "$FORGE_CONFIG" ]; then
    echo -e "${GREEN}✅ Forge config found${NC}"
    
    # Check if backend is configured as extra resource
    if grep -q "extraResource" "$FORGE_CONFIG"; then
        echo -e "${GREEN}✅ Backend configured as extra resource${NC}"
    else
        echo -e "${YELLOW}⚠️  Backend not configured as extra resource${NC}"
    fi
else
    echo -e "${RED}❌ Forge config not found${NC}"
fi

# Test 5: Check if DMG exists (if we're testing a completed build)
echo -e "${BLUE}🔍 Test 5: Build artifacts${NC}"
DMG_PATH="$PROJECT_ROOT/frontend/out/make/Erudi-Installer.dmg"
if [ -f "$DMG_PATH" ]; then
    echo -e "${GREEN}✅ DMG installer found${NC}"
    DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)
    echo -e "${BLUE}📊 DMG size: $DMG_SIZE${NC}"
else
    echo -e "${YELLOW}⚠️  DMG installer not found (run build first)${NC}"
fi

# Test 6: Check main.js for proper configuration
echo -e "${BLUE}🔍 Test 6: Main.js configuration${NC}"
MAIN_JS="$PROJECT_ROOT/frontend/src/main.js"
if [ -f "$MAIN_JS" ]; then
    echo -e "${GREEN}✅ Main.js found${NC}"
    
    # Check for environment variables
    if grep -q "DATABASE_URL" "$MAIN_JS"; then
        echo -e "${GREEN}✅ Environment variables configured${NC}"
    else
        echo -e "${RED}❌ Environment variables not configured${NC}"
    fi
    
    # Check for backend path resolution
    if grep -q "resolvePackagedBackendPath" "$MAIN_JS"; then
        echo -e "${GREEN}✅ Backend path resolution configured${NC}"
    else
        echo -e "${RED}❌ Backend path resolution not configured${NC}"
    fi
else
    echo -e "${RED}❌ Main.js not found${NC}"
fi

# Test 7: Quick syntax check of main files
echo -e "${BLUE}🔍 Test 7: Syntax checks${NC}"

# Check main.js syntax
if node -c "$MAIN_JS" 2>/dev/null; then
    echo -e "${GREEN}✅ Main.js syntax is valid${NC}"
else
    echo -e "${RED}❌ Main.js has syntax errors${NC}"
fi

# Check forge.config.js syntax
if node -c "$FORGE_CONFIG" 2>/dev/null; then
    echo -e "${GREEN}✅ Forge config syntax is valid${NC}"
else
    echo -e "${RED}❌ Forge config has syntax errors${NC}"
fi

echo -e "${BLUE}🏁 Test summary completed${NC}"

# Final recommendation
echo -e "\n${YELLOW}📋 Next steps:${NC}"
if [ -f "$DMG_PATH" ]; then
    echo -e "${GREEN}✅ Build appears complete! You can install the DMG.${NC}"
else
    echo -e "${YELLOW}💡 Run './build-scripts/build-erudi.sh' to create a complete build${NC}"
fi