#!/bin/bash
# Quick setup helper for Erudi build system
# Run this after copying build scripts from front-mac-build branch

echo "🚀 Erudi Build Setup Helper"
echo "=============================="
echo ""

# Check if we're in the right directory
if [ ! -f "BUILD.md" ]; then
    echo "❌ Error: Please run this script from the project root"
    exit 1
fi

echo "✅ In project root"
echo ""

# Check build scripts
echo "📋 Checking build scripts..."
if [ -f "build-scripts/build-erudi.sh" ]; then
    echo "  ✅ build-erudi.sh found"
    chmod +x build-scripts/*.sh 2>/dev/null
    echo "  ✅ Scripts made executable"
else
    echo "  ⚠️  Build scripts not found"
    echo "     Copy them from front-mac-build branch:"
    echo "     git checkout origin/front-mac-build -- build-scripts/"
fi
echo ""

# Check icons
echo "🎨 Checking icons..."
if [ -f "frontend/assets/icons/icon.png" ] || [ -f "frontend/assets/icons/icon.icns" ]; then
    echo "  ✅ Icons found"
else
    echo "  ⚠️  Icons not found"
    echo "     Quick fix: cp frontend/src/img/logo-erudi.png frontend/assets/icons/icon.png"
    echo "     Proper fix: See frontend/assets/icons/README.md"
fi
echo ""

# Check backend build
echo "🐍 Checking backend build..."
if [ -f "backend/dist/backend/backend" ]; then
    echo "  ✅ Backend executable exists"
else
    echo "  ⚠️  Backend not built"
    echo "     Build it:"
    echo "     cd backend && source venv/bin/activate && pyinstaller backend.spec"
fi
echo ""

# Check frontend dependencies
echo "📦 Checking frontend dependencies..."
if [ -d "frontend/node_modules" ]; then
    echo "  ✅ Frontend dependencies installed"
else
    echo "  ⚠️  Frontend dependencies not installed"
    echo "     Install them: cd frontend && npm install"
fi
echo ""

# Check if @electron-forge/maker-dmg is installed
if grep -q "@electron-forge/maker-dmg" frontend/package.json 2>/dev/null; then
    echo "  ✅ DMG maker installed"
else
    echo "  ⚠️  DMG maker not installed"
    echo "     Install it: cd frontend && npm install --save-dev @electron-forge/maker-dmg"
fi
echo ""

# Summary
echo "📊 Status Summary:"
echo "==================="

READY=true

if [ ! -f "build-scripts/build-erudi.sh" ]; then
    echo "❌ Build scripts missing"
    READY=false
fi

if [ ! -f "frontend/assets/icons/icon.png" ] && [ ! -f "frontend/assets/icons/icon.icns" ]; then
    echo "⚠️  Icons missing (optional but recommended)"
fi

if [ ! -f "backend/dist/backend/backend" ]; then
    echo "❌ Backend not built"
    READY=false
fi

if [ ! -d "frontend/node_modules" ]; then
    echo "❌ Frontend dependencies not installed"
    READY=false
fi

echo ""

if [ "$READY" = true ]; then
    echo "🎉 Ready to build!"
    echo ""
    echo "Next steps:"
    echo "  1. ./build-scripts/build-erudi.sh          # Full build"
    echo "  2. ./build-scripts/test-build.sh           # Verify build"
    echo "  3. open frontend/out/make/Erudi-Installer.dmg  # Test DMG"
    echo ""
    echo "For development:"
    echo "  ./build-scripts/dev-start.sh               # Start dev mode"
else
    echo "⏳ Setup incomplete"
    echo ""
    echo "Complete these steps:"
    echo ""
    if [ ! -f "build-scripts/build-erudi.sh" ]; then
        echo "1. Copy build scripts:"
        echo "   git checkout origin/front-mac-build -- build-scripts/"
        echo ""
    fi
    if [ ! -f "backend/dist/backend/backend" ]; then
        echo "2. Build backend:"
        echo "   cd backend"
        echo "   source venv/bin/activate"
        echo "   pyinstaller backend.spec"
        echo "   cd .."
        echo ""
    fi
    if [ ! -d "frontend/node_modules" ]; then
        echo "3. Install frontend dependencies:"
        echo "   cd frontend && npm install && cd .."
        echo ""
    fi
    if [ ! -f "frontend/assets/icons/icon.png" ] && [ ! -f "frontend/assets/icons/icon.icns" ]; then
        echo "4. Add icons (optional):"
        echo "   cp frontend/src/img/logo-erudi.png frontend/assets/icons/icon.png"
        echo ""
    fi
    echo "Then run this script again to verify setup"
fi
