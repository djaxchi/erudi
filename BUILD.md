# Building Erudi for Distribution

This guide explains how to build Erudi for deployment on macOS.

## Overview

Erudi is an Electron application with an embedded Python backend. The build process involves:
1. Building the Python backend with PyInstaller
2. Copying the backend into the frontend directory
3. Building the Electron app with the backend included
4. Creating a DMG installer

## Prerequisites

### Backend Requirements
- Python 3.11 or later
- Virtual environment (`venv`)
- All dependencies from `backend/requirements.txt`
- PyInstaller

### Frontend Requirements
- Node.js 18 or later
- npm
- All dependencies from `frontend/package.json`

## Build Process

### Option 1: Full Build (Recommended)

Use the automated build script:

```bash
./build-scripts/build-erudi.sh
```

or 
```bash
# Load your credentials
source .env.notarize

# Build with automatic signing & notarization
./build-scripts/build-erudi.sh
```
for notorization

with 

.env.notarize having

export APPLE_ID=
export APPLE_ID_PASSWORD=
export APPLE_TEAM_ID=
export APPLE_SIGNING_IDENTITY=



This will:
1. Build the backend with PyInstaller
2. Copy it to the frontend directory
3. Install frontend dependencies if needed
4. Build the Electron app
5. Create the DMG installer in `frontend/out/make/Erudi-Installer.dmg`

### Option 2: Manual Build

If you prefer to build manually or need more control:

#### Step 1: Build the Backend

```bash
cd backend

# Activate virtual environment
source venv/bin/activate

# Install PyInstaller if not already installed
pip install pyinstaller

# Build the backend
pyinstaller backend.spec
```

This creates `backend/dist/backend/` containing the executable and dependencies.

#### Step 2: Copy Backend to Frontend

```bash
cd ../frontend

# Remove old backend if exists
rm -rf backend/

# Copy new backend
cp -r ../backend/dist/backend ./backend
```

#### Step 3: Build Electron App

```bash
# Make sure dependencies are installed
npm install

# Build the app and create DMG
npm run make
```

The DMG will be created at `frontend/out/make/Erudi-Installer.dmg`.

### Option 3: Quick Backend Rebuild

If you only changed Python code and already have a frontend build:

```bash
./build-scripts/quick-backend-rebuild.sh
cd frontend
npm run make
```

## Development Mode

For development, you can run the app without building:

### Option 1: Using the Dev Script

```bash
./build-scripts/dev-start.sh
```

This automatically:
- Starts the Python backend
- Waits for it to be ready
- Launches the Electron app
- Cleans up when you exit

### Option 2: Manual Dev Setup

Terminal 1 - Backend:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2 - Frontend:
```bash
cd frontend
npm start
```

**Note:** In dev mode, the frontend expects a built backend at `backend/dist/backend/backend`. Build it once with PyInstaller if you haven't.

## Build Configuration Files

### Backend: `backend/backend.spec`

PyInstaller specification file that:
- Defines what to include in the backend bundle
- Specifies hidden imports for ML libraries
- Configures data files (models, configs, etc.)

Key sections:
- `datas`: Data files to include (torch, transformers, etc.)
- `hiddenimports`: Python modules that PyInstaller might miss
- `Analysis`: Entry point is `run_mac.py`

### Frontend: `frontend/forge.config.js`

Electron Forge configuration that:
- Bundles the backend as an extra resource
- Configures the DMG maker
- Sets app metadata and icons

Key settings:
```javascript
packagerConfig: {
  extraResource: ["./backend"],  // Include backend
  icon: "./assets/icons/icon",   // App icon
  // ... other metadata
}
```

### Frontend: `frontend/src/main.js`

Main Electron process that:
- Detects if app is packaged or in development
- Finds and spawns the backend executable
- Manages backend lifecycle
- Creates the application window

Key features:
- **Dev mode**: Looks for backend in `../backend/dist/backend/`
- **Build mode**: Looks for backend in packaged resources
- Logs to `/tmp/erudi-backend.log` for debugging
- Automatically shuts down backend on app exit

## Icon Setup

Place application icons in `frontend/assets/icons/`:

- `icon.icns` - macOS (required for proper DMG)
- `icon.ico` - Windows
- `icon.png` - Linux/fallback (512x512 recommended)

See `frontend/assets/icons/README.md` for icon creation instructions.

## Build Artifacts

After a successful build, you'll find:

```
frontend/
├── out/
│   ├── erudi-darwin-arm64/          # Unpacked app
│   │   └── erudi.app/
│   └── make/
│       └── Erudi-Installer.dmg      # Distributable DMG
```

The DMG file is what you distribute to users.

## Testing the Build

### Quick Test

```bash
./build-scripts/test-build.sh
```

This verifies:
- Backend executable exists and is correct architecture
- All dependencies are included
- Configuration files are correct
- DMG was created successfully

### Manual Test

1. **Test the packaged app directly:**
   ```bash
   open frontend/out/erudi-darwin-arm64/erudi.app
   ```

2. **Test the DMG installer:**
   ```bash
   open frontend/out/make/Erudi-Installer.dmg
   ```
   - Mount the DMG
   - Drag Erudi to Applications
   - Launch from Applications

3. **Check backend logs:**
   ```bash
   tail -f /tmp/erudi-backend.log
   ```

## Troubleshooting

### Backend Build Issues

**Error: "ModuleNotFoundError" when running packaged app**
- Add the missing module to `hiddenimports` in `backend.spec`
- Rebuild the backend

**Error: "Backend executable not found"**
- Ensure you built the backend with `pyinstaller backend.spec`
- Check that `backend/dist/backend/backend` exists
- Verify it was copied to `frontend/backend/`

### Frontend Build Issues

**Error: "Backend not starting"**
- Check `/tmp/erudi-backend.log` for backend errors
- Verify backend has execute permissions: `chmod +x frontend/backend/backend`
- On macOS, check System Settings > Privacy & Security for blocked executables

**Error: "DMG not created"**
- Ensure `@electron-forge/maker-dmg` is installed
- Check that `forge.config.js` includes the DMG maker
- Look for build errors in the terminal output

**Error: "Icon not found"**
- Place icons in `frontend/assets/icons/`
- Ensure files are named correctly (`icon.icns`, `icon.ico`, `icon.png`)
- Icon path in `forge.config.js` should be `./assets/icons/icon` (no extension)

### Runtime Issues

**App launches but can't connect to backend**
- Check if backend is running: `ps aux | grep backend`
- Check logs: `tail -f /tmp/erudi-backend.log`
- Verify port 8000 is not blocked

**macOS security warning about backend**
- On first run, macOS may block the unsigned backend binary
- Go to System Settings > Privacy & Security
- Click "Allow" next to the backend binary warning
- Relaunch the app

**Database/models not found**
- Backend expects `data/` directory relative to its location
- In packaged app, this is inside the backend bundle
- Check working directory is set correctly in `main.js`

## File Size Considerations

The built DMG will be large (300-500MB+) because it includes:
- Complete Python runtime
- PyTorch and ML libraries
- Transformers models cache
- All dependencies

This is normal for ML applications with embedded Python.

## Distribution Checklist

Before distributing the DMG:

- [ ] Backend builds successfully
- [ ] Frontend builds successfully
- [ ] DMG is created
- [ ] Icons are properly set
- [ ] App launches from DMG
- [ ] Backend starts and responds
- [ ] Can create/load conversations
- [ ] Can download models
- [ ] Can run inference
- [ ] Test on a fresh Mac (if possible)
- [ ] Update version numbers in `package.json` and `forge.config.js`

## Environment Variables

The backend is spawned with these environment variables (set in `main.js`):

```javascript
DATABASE_URL: "sqlite:///./data/erudi.db"
CACHE_DIR: "./data/models_cache"
INDEXES_DIR: "./data/indexes"
```

These are relative to the backend's working directory.

## Code Signing (Optional)

For distribution outside of development, you should code sign the app:

1. Get an Apple Developer certificate
2. Add to `forge.config.js`:
   ```javascript
   packagerConfig: {
     osxSign: {
       identity: 'Developer ID Application: Your Name (TEAM_ID)',
     },
     osxNotarize: {
       appleId: 'your-apple-id@example.com',
       appleIdPassword: '@keychain:AC_PASSWORD',
     },
   }
   ```

Without code signing, users will see security warnings on first launch.

## Next Steps

After building successfully:

1. Test the DMG on multiple Macs if possible
2. Consider code signing for easier distribution
3. Create release notes
4. Upload to distribution platform or share DMG directly

## Support

For build issues:
- Check `/tmp/erudi-backend.log` for backend errors
- Check Electron console (Cmd+Option+I in dev mode)
- Run `./build-scripts/test-build.sh` for diagnostics
