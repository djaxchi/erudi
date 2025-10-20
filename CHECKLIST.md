# Build Implementation Checklist

## ✅ Completed

- [x] Updated `frontend/src/main.js` with backend spawning logic
- [x] Updated `frontend/forge.config.js` with build configuration
- [x] Installed `@electron-forge/maker-dmg` dependency
- [x] Created documentation (`BUILD.md`, `BUILD_IMPLEMENTATION.md`)
- [x] Created icon directory and guide (`frontend/assets/icons/README.md`)
- [x] Updated `.gitignore` for build artifacts
- [x] Created `build-scripts/` directory

## ⏳ To Do

### 1. Add Build Scripts
Copy these from `front-mac-build` branch to `build-scripts/`:
- [ ] `build-erudi.sh` - Main build script
- [ ] `dev-start.sh` - Development startup script  
- [ ] `quick-backend-rebuild.sh` - Fast backend rebuild
- [ ] `test-build.sh` - Build verification script
- [ ] `README.md` - Scripts documentation

**How to copy:**
```bash
git checkout origin/front-mac-build -- build-scripts/
# Or copy files manually from the branch
```

### 2. Create Application Icons
- [ ] Choose source logo from `frontend/src/img/`
- [ ] Create `icon.icns` for macOS (see `frontend/assets/icons/README.md`)
- [ ] Create `icon.png` as fallback (512x512 recommended)
- [ ] Place icons in `frontend/assets/icons/`

**Quick method:**
```bash
# Copy a logo as the base icon
cp frontend/src/img/logo-erudi.png frontend/assets/icons/icon.png

# For proper macOS icon, follow the iconset creation in:
# frontend/assets/icons/README.md
```

### 3. Test Backend Build
- [ ] Build backend with PyInstaller
  ```bash
  cd backend
  source venv/bin/activate
  pyinstaller backend.spec
  ```
- [ ] Verify backend executable exists at `backend/dist/backend/backend`
- [ ] Test backend can start manually:
  ```bash
  ./backend/dist/backend/backend --port 8000
  ```

### 4. Test Development Mode
- [ ] Copy backend to frontend for dev testing:
  ```bash
  rm -rf frontend/backend/
  cp -r backend/dist/backend frontend/backend
  ```
- [ ] Start frontend:
  ```bash
  cd frontend
  npm start
  ```
- [ ] Verify backend spawns automatically
- [ ] Check `/tmp/erudi-backend.log` for logs
- [ ] Test basic functionality (chat, models, etc.)

### 5. Test Full Build
- [ ] Ensure backend is in `frontend/backend/`
- [ ] Run Electron build:
  ```bash
  cd frontend
  npm run make
  ```
- [ ] Verify DMG created at `frontend/out/make/Erudi-Installer.dmg`
- [ ] Test app from unpacked build:
  ```bash
  open frontend/out/erudi-darwin-arm64/erudi.app
  ```

### 6. Test DMG Installation
- [ ] Open the DMG: `open frontend/out/make/Erudi-Installer.dmg`
- [ ] Drag app to Applications
- [ ] Launch from Applications
- [ ] Allow backend in macOS Security settings if prompted
- [ ] Verify app works correctly
- [ ] Test all major features

### 7. Final Verification
- [ ] Backend starts automatically
- [ ] Frontend connects to backend
- [ ] Can download models
- [ ] Can create conversations
- [ ] Can chat with models
- [ ] Knowledge base works
- [ ] Training works
- [ ] Data persists across restarts

## Quick Reference Commands

### Build Backend Only
```bash
cd backend && source venv/bin/activate && pyinstaller backend.spec
```

### Copy Backend to Frontend
```bash
cd frontend && rm -rf backend/ && cp -r ../backend/dist/backend ./backend
```

### Build Full App
```bash
cd frontend && npm run make
```

### Test App
```bash
open frontend/out/erudi-darwin-arm64/erudi.app
```

### View Logs
```bash
tail -f /tmp/erudi-backend.log
```

### Clean Build Artifacts
```bash
rm -rf frontend/out/ frontend/backend/ backend/dist/ backend/build/
```

## Troubleshooting Quick Fixes

### Backend won't start
1. Check logs: `tail -f /tmp/erudi-backend.log`
2. Verify executable exists: `ls -la frontend/backend/backend`
3. Check permissions: `chmod +x frontend/backend/backend`

### Build fails
1. Clean and rebuild: `rm -rf frontend/out/ && npm run make`
2. Check backend exists: `ls -la frontend/backend/`
3. Verify dependencies: `cd frontend && npm install`

### DMG not created
1. Verify DMG maker is installed: `npm list @electron-forge/maker-dmg`
2. Check `forge.config.js` has DMG maker configured
3. Look for errors in build output

### Icons not showing
1. Verify icons exist: `ls -la frontend/assets/icons/`
2. Check icon path in `forge.config.js`: `./assets/icons/icon`
3. Rebuild with icons in place

## Notes

- **First backend build is slow** (includes all ML libraries)
- **DMG will be 300-500MB** (normal for ML apps)
- **macOS will warn about unsigned app** (user must allow in Security settings)
- **Dev mode needs backend built once** (doesn't rebuild automatically)
- **Logs are your friend** (`/tmp/erudi-backend.log` for debugging)

## Success Criteria

The build is ready when:
- ✅ DMG installs successfully
- ✅ App launches without errors
- ✅ Backend starts automatically
- ✅ All features work
- ✅ Data persists
- ✅ No console errors
