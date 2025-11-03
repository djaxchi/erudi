# Build Implementation Checklist

## 🎨 Frontend Refactoring Progress

### Phase 1-2: Infrastructure & Console Migration ✅ COMPLETE
- [x] ESLint + Prettier configuration
- [x] Logger utility implementation
- [x] API client setup
- [x] Custom hooks creation
- [x] Console migration (96+ calls → logger, 94% reduction)

### Phase 3: PropTypes & Code Cleanup 🚧 IN PROGRESS
**Checkpoint: 2025-11-03**

**✅ Completed:**
- [x] Added PropTypes to 21/28 components (75% complete)
  - Dropdown, GradientBox, HardwareInfo, HeaderBar, QuestionInput
  - Sidebar, ConfirmationModal, Tooltip, Spinner, TypingIndicator, LoadingScreen
- [x] Cleaned up unused variables & imports
  - Removed unused lucide-react imports (Cog, X, Check, Folder)
  - Removed unused PropTypes imports from 6 pages (ArenaPage, ChatPage, etc.)
  - Removed unused useRef, backgroundClass parameter
- [x] Reduced ESLint issues: **385 → 304** (21% reduction)
- [x] Reduced PropTypes warnings: **189 → 100** (47% reduction)
- [x] Git commits: `1f02438`, `22fc458`

**⏳ Remaining Phase 3 Tasks:**
- [ ] Complete PropTypes for 7 remaining components (DatasetCard, TrainNewModelCard, modals)
- [ ] Fix ~100 remaining PropTypes warnings (nested props)
- [ ] Fix ~40 HTML entity warnings (apostrophes in JSX)
- [ ] Fix ~10 hook dependency warnings (exhaustive-deps)
- [ ] Continue unused variable cleanup (verify with grep to avoid false positives)

**📋 Next Phases:**
- Phase 4: Extract business logic to services
- Phase 5: Implement Zustand state management
- Phase 6+: Page refactoring, performance optimization, accessibility

---

## ✅ Completed

- [x] Updated `frontend/src/main.js` with backend spawning logic
- [x] Updated `frontend/forge.config.js` with build configuration
- [x] Installed `@electron-forge/maker-dmg` dependency
- [x] Created documentation (`BUILD.md`, `BUILD_IMPLEMENTATION.md`)
- [x] Created icon directory and guide (`frontend/assets/icons/README.md`)
- [x] Updated `.gitignore` for build artifacts
- [x] Created `build-scripts/` directory
- [x] Implemented `backend/run.py` launcher with JSON event emission
- [x] Implemented `backend/src/launcher/runtime_paths.py` for cross-platform path resolution
- [x] Added OS-specific directory handling (macOS Library, Windows AppData, Linux XDG)
- [x] **Created `backend/backend.spec`** for PyInstaller with multi-variant support
- [x] **Created `scripts/build/build-backend.sh`** for reproducible backend builds
- [x] **Created `backend/backend-cpu.spec`** for CPU-only variant
- [x] **Created `.github/workflows/backend-ci.yml`** for backend lint, type-check, test, and coverage
- [x] **Fixed launcher port argument mismatch**: `run.py` now accepts `--port` argument
- [x] **Added `backend/tests/test_launcher.py`** for argument parsing and event emission tests

## 🚨 Critical Issues (Blocking Release)

### Launcher System Fixes

- [x] **Create missing `backend/backend.spec`** for PyInstaller
  - ✅ DONE: Consolidated multi-variant spec with artifact auto-inclusion and runtime hooks

- [x] **Fix port argument mismatch**
  - ✅ DONE: `run.py` now accepts `--port` argument; properly emits port in JSON events

- [x] **Add launcher test coverage**
  - ✅ DONE: `backend/tests/test_launcher.py` tests argument parsing and event emission

### New Critical Tasks

- [ ] **Audit & merge tmp_win directories** (P0)
  - Compare `tmp_winStartupErrorHandle/` and `tmp_win_cu12/` against main `run.py` and `main.js`
  - Identify improvements/fixes that may not be in main branch
  - Cherry-pick any valuable changes back into main codebase
  - Test both versions to ensure no regressions
  - Remove temp directories after verification
  - Reference: Check `run.py` and `main.js` diffs against temp dir variants

- [ ] **Add runtime secrets management** (P0)
  - Create `backend/src/config/secrets.py` for environment variable injection
  - Support HF_TOKEN and other sensitive values built at runtime/CI time
  - Add to `.gitignore` to prevent accidental commits
  - Safely inject into app on startup
  - Reference: Build-time secret injection best practices

## ⏳ To Do

### 0. Infrastructure & Setup Tasks (P0)

- [ ] **Install pre-commit and hooks**
  - Add `.pre-commit-config.yaml` (already created with black, ruff, mypy, pytest)
  - Run `pre-commit install` to set up git hooks
  - Ensures code quality on every commit

### 1. Launcher Code Quality Improvements

- [ ] **Remove unused environment variables from `main.js`**
  - Lines 167-171 set `DATABASE_URL`, `CACHE_DIR`, `INDEXES_DIR`
  - `runtime_paths.py` ignores these completely
  - Dead code creating confusion

- [ ] **Use OS-assigned ports to eliminate conflicts**
  - Current: `run.py` checks port once, race condition if taken
  - Solution: Bind uvicorn to port 0, emit actual port in JSON event
  - Update `main.js` to parse port from JSON instead of hardcoding 8000

- [ ] **Bridge JSON events into logging system**
  - `run.py` uses `print()` for JSON events
  - Rest of app uses `src.core.logging.logger`
  - Startup errors invisible to log files
  - Add structured logging for launcher events

- [ ] **Review macOS symlink notarization impact**
  - `_ensure_macos_symlink` modifies packaged app bundle at runtime
  - May break code signing/notarization
  - Document limitations or remove if incompatible

### 2. Add Build Scripts
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

### 3. Create Application Icons
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

### 4. Test Backend Build
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

### 5. Test Development Mode
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

### 6. Test Full Build
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

### 7. Test DMG Installation
- [ ] Open the DMG: `open frontend/out/make/Erudi-Installer.dmg`
- [ ] Drag app to Applications
- [ ] Launch from Applications
- [ ] Allow backend in macOS Security settings if prompted
- [ ] Verify app works correctly
- [ ] Test all major features

### 8. Final Verification
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

## ⚡ Backend Runtime Optimizations

### Database & ORM Performance

- [ ] **Add database connection pooling configuration**
  - Current: Single-threaded connection mode with `check_same_thread=False`
  - Impact: Connection overhead on each request
  - Solution: Configure pool size, overflow, and recycling in `SessionLocal`
  - Files: `src/database/core.py`

- [ ] **Optimize N+1 query patterns with eager loading**
  - Issue: Multiple `.query().filter().first()` calls without joins
  - Found in: repositories across all domains
  - Solution: Use `.options(joinedload())` or `.options(selectinload())`
  - Priority areas: conversations with messages, LLMs with KB relationships

- [ ] **Add query result caching for static/read-heavy data**
  - Candidates: startup variables (singleton), hardware profiles, base model list
  - No current caching implementation found
  - Solution: Use `@lru_cache` or simple dict cache with TTL
  - Files: `src/domains/startup/repository.py`, `src/database/seed.py`

- [ ] **Implement bulk operations for batch updates**
  - Current: Individual `.add()` + `.commit()` in loops
  - Found in: seed operations, conversation message creation
  - Solution: Use `db.bulk_insert_mappings()` or `db.bulk_update_mappings()`
  - Files: `src/database/seed.py`, conversation repositories

### File I/O & Processing

- [ ] **Stream large file processing instead of loading entire files**
  - Issue: `open().read()` loads entire file into memory
  - Found in: `src/utils/file_processor.py` (PDF extraction, text cleaning)
  - Risk: OOM with large PDFs (>500MB)
  - Solution: Process files in chunks with generators

- [ ] **Add file processing progress tracking**
  - Current: Logs after completion, no intermediate progress
  - Impact: User sees no feedback during long operations
  - Solution: Yield progress percentages during chunking/embedding
  - Files: `src/utils/file_processor.py`, KB services

- [ ] **Optimize sentence splitting regex compilation**
  - Issue: Regex compiled on every `split_sentences()` call
  - Solution: Move `SENT_SPLIT_RE` to module level as constant
  - File: `src/utils/file_processor.py` line ~80

- [ ] **Cache tokenizer instances across requests**
  - Issue: `chunk_by_tokens()` may re-instantiate tokenizer
  - Solution: Module-level singleton with lazy loading
  - File: `src/utils/file_processor.py`

### Memory Management & Caching

- [ ] **Review ConversationCache singleton memory footprint**
  - Current: Unbounded in-memory storage for embeddings + FAISS indexes
  - Risk: Memory leak on servers with thousands of conversations
  - Solution: Implement LRU eviction policy with max cache size
  - File: `src/domains/conversations/utils/cache.py`

- [ ] **Add FAISS index serialization to disk**
  - Current: FAISS indexes kept in RAM, rebuilt on restart
  - Impact: Slow startup after crash/restart with large KBs
  - Solution: Persist to `INDEXES_DIR`, load on demand
  - Files: `src/domains/knowledge_base/services.py`

- [ ] **Optimize embedding batch sizes**
  - Current: Processes embeddings individually or in small batches
  - Solution: Batch documents for embedding (e.g., 32-64 at a time)
  - Impact: ~3-5x speedup on KB indexing
  - File: `src/domains/knowledge_base/services.py`

- [ ] **Clear unused model instances from engine cache**
  - Current: Models cached indefinitely in `_model_cache`
  - Issue: No LRU eviction, grows unbounded
  - Solution: Implement max cache size (e.g., 3 models) with LRU
  - Files: All engine files (`src/engines/`)

### Async/Concurrency Improvements

- [ ] **Make file processing operations truly async**
  - Issue: Blocking I/O wrapped in `run_in_threadpool()` instead of async I/O
  - Found in: PDF extraction, text file reading
  - Solution: Use `aiofiles` for async file operations
  - Files: `src/utils/file_processor.py`, KB endpoints

- [ ] **Parallelize PDF batch processing**
  - Current: Sequential processing in `prepare_for_knowledge_base()`
  - Solution: Use `asyncio.gather()` with `ProcessPoolExecutor` for CPU-bound work
  - Impact: ~4x speedup on multi-file KB creation
  - File: `src/utils/file_processor.py`

- [ ] **Add request-level caching for repeated LLM lookups**
  - Issue: Same `get_llm_by_id()` called multiple times per request
  - Solution: Use FastAPI dependency with `@lru_cache` or request state
  - Files: Service layers across domains

### Engine & Model Loading

- [ ] **Implement lazy model loading**
  - Current: Models loaded on first request, blocking response
  - Solution: Pre-warm cache on startup for default model
  - Add `/llms/{id}/warmup` endpoint for explicit preloading
  - Files: `src/engines/base_engine.py`

- [ ] **Add model unloading API**
  - Current: No way to free model memory without restart
  - Solution: Add `/llms/{id}/unload` endpoint to clear from cache
  - Use case: Free VRAM when switching between large models
  - Files: All engine files

- [ ] **Optimize tokenizer caching**
  - Issue: Tokenizers loaded on every `get_model_and_tokenizer()` call
  - Solution: Separate tokenizer cache from model cache (lighter weight)
  - Impact: Faster conversation starts when model already loaded
  - Files: `src/engines/base_engine.py`

- [ ] **Remove redundant torch imports**
  - Issue: `import torch` called inside functions (e.g., `is_cuda_available()`)
  - Solution: Move to module level or lazy import at class level
  - Impact: Faster engine selection on startup
  - Files: `src/engines/mlx_engine.py`, `src/engines/cuda_engine.py`

### Streaming & Response Time

- [ ] **Implement streaming response buffering**
  - Current: Single-token yields cause high HTTP overhead
  - Solution: Buffer 3-5 tokens before yielding
  - Impact: Reduce network latency, smoother frontend rendering
  - Files: Engine `generate_stream()` methods

- [ ] **Add generation timeout configuration**
  - Current: No timeout on generation loops
  - Risk: Infinite loops on model errors
  - Solution: Add configurable timeout (default 120s) with graceful termination
  - Files: All engine files, conversation services

- [ ] **Optimize prompt formatting overhead**
  - Issue: Chat template applied on every streaming chunk
  - Solution: Pre-compute formatted prompt, reuse across chunks
  - Files: Engine `generate_stream()` implementations

### Logging & Monitoring

- [ ] **Reduce excessive debug logging in hot paths**
  - Issue: `logger.debug()` calls in tight loops (sentence splitting, chunking)
  - Solution: Log only summaries, use `logger.isEnabledFor(DEBUG)` guards
  - Impact: ~10-15% speedup in text processing
  - Files: `src/utils/file_processor.py`

- [ ] **Add performance metrics endpoints**
  - Missing: No way to track request latency, throughput, cache hit rates
  - Solution: Add `/metrics` endpoint with Prometheus-compatible format
  - Metrics: request_duration, model_load_time, cache_hit_rate, queue_depth
  - Files: New `src/core/metrics.py`

- [ ] **Implement structured logging for performance events**
  - Current: Text-based logs hard to parse
  - Solution: Add JSON logging mode with duration/bytes fields
  - Use case: Analyze slow requests, identify bottlenecks
  - Files: `src/core/logging.py`

### Configuration & Tuning

- [ ] **Make chunk sizes configurable**
  - Current: Hardcoded 512 tokens, 15% overlap
  - Solution: Add to app config or per-KB settings
  - Use case: Tune for different embedding models or use cases
  - Files: `src/utils/file_processor.py`, `src/core/config.py`

- [ ] **Add FAISS index type selection**
  - Current: Always `IndexFlatL2` (brute force, exact)
  - Solution: Support `IndexIVFFlat` for large KBs (approximate, faster)
  - Threshold: Switch to IVF when vectors > 10,000
  - Files: `src/domains/knowledge_base/services.py`

- [ ] **Configure embedding model selection**
  - Current: Hardcoded `paraphrase-multilingual-MiniLM-L12-v2`
  - Solution: Add to config, allow per-KB selection
  - Options: Faster (MiniLM-L6), more accurate (mpnet-base)
  - Files: `src/engines/embedder_engine.py`, `src/core/config.py`

## 🏗️ Build & Launch Infrastructure Optimizations

### Cross-Platform Path Consistency

- [ ] **Fix venv path bug in `tmp_win_cu12/main.js`**
  - Issue: Lines reference macOS path `venv/bin/python` in Windows launcher
  - Current: Should use `venv/Scripts/python.exe` for Windows
  - Impact: Backend fails to start on Windows CUDA 12.1 builds
  - Files: `tmp_win_cu12/main.js` lines ~150-160

- [ ] **Standardize backend executable paths across launchers**
  - Current: Three different path resolution strategies across launcher variants
  - `frontend/src/main.js`: Uses `resolvePackagedBackendPath()` with 3 candidates
  - `tmp_winStartupErrorHandle/main.js`: Uses `venv/Scripts/python.exe backend.exe`
  - `tmp_win_cu12/main.js`: Uses incorrect `venv/bin/python` (macOS path)
  - Solution: Create shared path resolution module or consolidate launchers

- [ ] **Remove hardcoded project paths in build scripts**
  - Issue: `scripts/build/mac/build-full-mac-silicon.sh` line 40: `PROJECT_ROOT="/Users/djadja/Code/erudi"`
  - Impact: Script fails on any other machine
  - Solution: Use `git rev-parse --show-toplevel` or relative path from script location
  - Files: `scripts/build/mac/build-full-mac-silicon.sh`

- [ ] **Unify data directory resolution across platforms**
  - Current: Multiple implementations of data folder logic
  - `frontend/src/main.js`: `getDataDirectory()` function (lines ~400+)
  - `backend/src/launcher/runtime_paths.py`: Platform-specific paths
  - Risk: Inconsistent behavior between Electron and Python backend
  - Solution: Backend should be single source of truth, Electron queries via API

### Build Script Consolidation

- [ ] **Create unified multi-platform build orchestrator**
  - Current: Separate scripts for each platform (Windows: Node.js, macOS: Bash)
  - Scripts: `scripts/build/windows/build-full.js`, `scripts/build/mac/build-full-mac-silicon.sh`
  - Problem: Duplicated logic, inconsistent error handling, no Linux support
  - Solution: Single Node.js orchestrator with platform detection (works everywhere)
  - Benefits: DRY principle, consistent logging, easier CI/CD integration

- [ ] **Extract common PyInstaller logic**
  - Current: `scripts/build/windows/build-backend.js` has sophisticated Python detection
  - Duplicated: macOS script has similar but different version checking
  - Solution: Create `scripts/build/common/pyinstaller-build.js` module
  - Features: Python version detection, venv management, requirement installation, spec file execution

- [ ] **Add PyInstaller spec file generator**
  - Issue: No `backend.spec` file exists in repository (confirmed via file search)
  - Current: Build scripts call `pyinstaller backend.spec` but file missing
  - Impact: Builds will fail on fresh clones
  - Solution: Generate spec file programmatically or commit template to repo
  - Must include: All dependencies, data files (models, indexes), hidden imports (transformers, torch)

- [ ] **Implement engine-variant builds**
  - Current: Single monolithic build includes all dependencies (MLX + CUDA + CPU)
  - Problem: ~500MB+ installers even for CPU-only users
  - Solution: Create separate build configs for each backend type:
    - `build --variant=mac-silicon` (MLX only, ~200MB)
    - `build --variant=windows-cuda-12` (CUDA 12.1, ~400MB)
    - `build --variant=windows-cpu` (CPU only, ~150MB)
  - Requires: Conditional dependency installation in PyInstaller spec

### Setup Script Optimization

- [ ] **Eliminate setup script duplication (80%+ code reuse)**
  - Current: 11 nearly-identical setup scripts in `scripts/dev/backend/`
  - Variants: Mac (Silicon/Intel), Windows (CPU/CUDA 11.8/12.1), Linux (CPU/CUDA 11.8/12.1)
  - Common logic: Python version check, venv creation, dev/prod selection, requirement installation
  - Solution: Create `scripts/dev/backend/setup-base.sh` with platform/engine parameters
  - Example: `./setup-base.sh --platform=mac --arch=silicon --engine=mlx --mode=dev`

- [ ] **Add interactive platform detection for setup scripts**
  - Current: User must manually choose correct script from 11 options
  - Problem: Confusing for new contributors, easy to select wrong variant
  - Solution: Single `scripts/dev/backend/setup.sh` entry point
  - Behavior: Auto-detect OS/arch, prompt for engine type (CUDA version if Windows), run appropriate setup
  - Fallback: Manual override flags for CI environments

- [ ] **Standardize dev/prod mode selection**
  - Current: Different implementations across scripts
  - Mac scripts: Interactive prompt or `CI=true` env var
  - Windows scripts: `-Mode` parameter (dev/prod)
  - Solution: Unified approach using env vars: `ERUDI_ENV=dev|prod`, fallback to interactive

- [ ] **Add setup script validation and health checks**
  - Missing: No verification that setup succeeded before user starts development
  - Add: Post-install validation (Python version, import torch/mlx, check GPU)
  - Add: Print environment summary (Python version, CUDA version, available GPUs)
  - Files: All setup scripts in `scripts/dev/backend/`

### Electron Forge Configuration

- [ ] **Implement code signing configuration**
  - Current: Commented placeholders in `forge.config.js` (frontend and tmp dirs)
  - Needed for: macOS notarization, Windows SmartScreen bypass
  - Requirements: Developer certificates, credential management
  - Files: `frontend/forge.config.js`, `tmp_winStartupErrorHandle/forge.config.js`, `tmp_win_cu12/forge.config.js`

- [ ] **Configure auto-update infrastructure**
  - Current: `autoUpdater` configuration commented out
  - Missing: Update server, release channel management, differential updates
  - Solution: Implement Electron's autoUpdater with GitHub Releases or custom server
  - Files: All `forge.config.js` files

- [ ] **Add ASAR integrity validation**
  - Current: `asar: true` without integrity checks
  - Risk: Users can modify bundled frontend code
  - Solution: Enable ASAR integrity in Electron Fuses or add runtime validation
  - File: `frontend/forge.config.js` lines ~30-35

- [ ] **Optimize ASAR exclusions for performance**
  - Current: Only `.webpack` excluded from ASAR
  - Problem: Large files in ASAR slow startup (decompression overhead)
  - Solution: Exclude backend executable, models, datasets from ASAR packaging
  - Add: `"unpack": "backend/**/*,data/models/**/*"`

### Windows-Specific Improvements

- [ ] **Consolidate Windows launcher variants**
  - Current: Two separate implementations
  - `tmp_winStartupErrorHandle/`: Enhanced error detection, 35s timeout
  - `tmp_win_cu12/`: CUDA 12.1 specific, granular dep errors, 120s timeout
  - Decision needed: Merge both or keep CUDA version separate?
  - Recommendation: Merge with `--cuda-version` flag for conditional logic

- [ ] **Standardize GPU error detection across Windows launchers**
  - Current: Different error code enums
  - `tmp_winStartupErrorHandle/`: `GPU_DRIVER_MISSING`, `CUDA_VERSION_MISMATCH`, `NO_NVIDIA_GPU`
  - `tmp_win_cu12/`: `PYNVML_MISSING`, `PYTORCH_MISSING`, `BITSANDBYTES_MISSING`, etc.
  - Solution: Unified error taxonomy across both launchers + backend `run.py`

- [ ] **Implement NSIS uninstall cleanup improvements**
  - Current: `uninstall_cleanup.nsh` only removes `resources/` folder
  - Missing: User data folder cleanup (optional), registry cleanup, start menu shortcuts
  - Add: Prompt user to delete data folder during uninstall
  - File: `scripts/build/windows/uninstall_cleanup.nsh`

- [ ] **Add Windows installer customization**
  - Current: Minimal NSIS config in `forge.config.js`
  - Missing: Custom install wizard pages, license agreement, component selection
  - Add: Option to install for all users vs current user
  - Add: Desktop/start menu shortcut options
  - Files: `tmp_winStartupErrorHandle/forge.config.js`, `tmp_win_cu12/forge.config.js`

### macOS-Specific Improvements

- [ ] **Complete DMG maker configuration**
  - Current: Basic DMG config in `frontend/forge.config.js`
  - Missing: Custom background image, icon positioning, window size/position
  - Add: Branded DMG with drag-to-Applications visual
  - Reference: Electron Forge DMG maker documentation

- [ ] **Implement macOS notarization workflow**
  - Required: Submit builds to Apple for notarization
  - Prevents: Gatekeeper warnings on macOS 10.15+
  - Setup: Developer ID certificate, app-specific password, `notarytool`
  - Script: Add `scripts/build/mac/notarize.js` for automation

- [ ] **Address code signing compatibility with runtime symlinks**
  - Issue: `runtime_paths.py._ensure_macos_symlink()` modifies app bundle post-signing
  - Risk: Breaks signature, app won't open on strict security settings
  - Investigation: Test on macOS with hardened runtime enabled
  - Solution: Either remove symlinks or adjust signing entitlements

- [ ] **Add Mac Intel build support**
  - Current: Build script hardcoded to `arm64` architecture
  - Script: `scripts/build/mac/build-full-mac-silicon.sh` line references
  - Need: Separate script or `--arch` flag for `x86_64` builds
  - Universal binary: Consider lipo to merge both architectures

### Development Workflow Enhancements

- [ ] **Unify npm scripts across package.json variants**
  - Current: Different scripts in `frontend/`, `tmp_winStartupErrorHandle/`, `tmp_win_cu12/`
  - `frontend/package.json`: No `backend` or `build-full` scripts
  - Windows variants: Include `backend`, `frontend`, `build-full` scripts
  - Solution: Standardize scripts, ensure all variants have same interface

- [ ] **Create hot-reload support for backend in dev mode**
  - Current: `scripts/dev/dev-start.sh` starts backend in separate Terminal window
  - Problem: Manual restart needed after backend code changes
  - Solution: Integrate `watchdog` or `nodemon` to auto-restart on Python file changes
  - Benefit: Faster iteration cycle for developers

- [ ] **Add pre-build validation script**
  - Missing: No checks before starting lengthy build process
  - Checks: Python version, node version, required tools (PyInstaller, iconutil)
  - Checks: Required files exist (backend.spec, icons, README)
  - Script: `scripts/build/validate-environment.js` called by build orchestrator

- [ ] **Implement build artifact caching**
  - Current: Full rebuild every time (10-20 minutes)
  - Optimization: Cache PyInstaller build folder, npm node_modules
  - CI benefit: Reduce build times from 20min → 5min
  - Tools: GitHub Actions cache, ccache for native extensions

### Error Handling & Diagnostics

- [ ] **Standardize launcher error event format**
  - Current: `run.py` emits JSON events with `type` and `message`
  - Windows launchers: Parse stderr for specific GPU error patterns
  - Problem: No shared error code taxonomy between backend and Electron
  - Solution: Define error code enum (e.g., `ERR_PORT_IN_USE`, `ERR_GPU_NOT_FOUND`)
  - Implement: Backend emits codes in JSON, Electron displays user-friendly messages

- [ ] **Add launcher diagnostics endpoint**
  - Create: `POST /launcher/diagnostics` endpoint in backend
  - Returns: System info (Python version, GPU status, disk space, dependencies)
  - Use case: Electron calls on startup failure, includes in error reports
  - File: New `src/domains/launcher/api.py`

- [ ] **Implement structured error logging for build failures**
  - Current: Build scripts use `console.log()` with mixed formatting
  - Problem: Hard to parse failures in CI logs
  - Solution: Use structured logging library (winston for Node.js)
  - Add: Error codes, timestamps, context (file being built, step number)

- [ ] **Create build failure recovery guide**
  - Document: Common build errors and solutions
  - Topics: Missing Python, PyInstaller errors, icon conversion failures, signing issues
  - Location: `docs/guides/build-troubleshooting.md`
  - Link: From build script error messages to specific doc sections

### Testing & Validation

- [ ] **Add build smoke tests**
  - Current: No automated validation after build completes
  - Tests: App launches, backend starts, health endpoint responds, basic chat works
  - Platform: Run on macOS, Windows, Linux in CI
  - Tool: Spectron (Electron testing framework) or Playwright

- [ ] **Create cross-platform launcher test suite**
  - Missing: No tests for Electron launcher logic (`main.js`)
  - Tests: Backend spawn, health checks, error detection, port conflicts, watchdog timeout
  - Mock: Backend process with controlled failure modes
  - Files: `frontend/tests/main.test.js`

- [ ] **Add PyInstaller bundle tests**
  - Verify: All imports work, no missing dependencies, data files accessible
  - Test: Run backend executable with `--help`, check imports, query test endpoint
  - Catch: Missing hidden imports before distribution
  - Script: `scripts/build/test-bundle.sh`

- [ ] **Implement installation end-to-end tests**
  - Automate: Full install → launch → basic operations → uninstall
  - Platforms: Test on clean VMs for macOS, Windows, Linux
  - Validate: No leftover files after uninstall, no permission errors
  - Tool: Vagrant or GitHub Actions with matrix builds

### Documentation & Maintainability

- [ ] **Document build system architecture**
  - Create: `docs/guides/build-system.md`
  - Cover: Directory structure, script purposes, execution flow, customization points
  - Diagrams: Build pipeline flowchart, launcher lifecycle, error handling paths
  - Audience: New contributors, release managers

- [ ] **Add inline documentation to build scripts**
  - Current: Minimal comments in `build-full.js`, `build-backend.js`
  - Add: Function-level docstrings, complex logic explanations
  - Explain: Why certain workarounds exist (e.g., Python version requirements)
  - Files: All scripts in `scripts/build/` and `scripts/dev/`

- [ ] **Create release checklist**
  - Document: Pre-release validation steps
  - Checklist: Version bumps, changelog updates, build all platforms, test installers, sign/notarize
  - Location: `docs/guides/release-process.md`
  - Automate: GitHub Actions workflow for release preparation

- [ ] **Standardize version numbering across package.json files**
  - Current: `frontend/package.json` = v1.0.0, Windows variants = v0.1.0
  - Problem: Version drift between development branches
  - Solution: Single source of truth (root `package.json` or `version.json`)
  - Script: `scripts/sync-version.js` to propagate version changes

### CI/CD Integration

- [ ] **Set up automated multi-platform builds**
  - Platforms: macOS (Silicon + Intel), Windows (CPU + CUDA 11.8 + CUDA 12.1), Linux (CPU + CUDA)
  - Trigger: On release tag creation or manual workflow dispatch
  - Upload: Build artifacts to GitHub Releases automatically
  - Tool: GitHub Actions with matrix strategy

- [ ] **Add build caching to CI pipeline**
  - Cache: PyInstaller dist, node_modules, pip packages
  - Benefit: Reduce CI build time from 30min → 8-10min
  - Implementation: GitHub Actions cache action with smart invalidation keys

- [ ] **Implement automated signing in CI**
  - Setup: Store certificates/credentials as GitHub Secrets
  - macOS: Certificate + app-specific password for notarization
  - Windows: Code signing certificate for Authenticode
  - Security: Use separate signing service or GitHub's OIDC

- [ ] **Add deployment workflow for update server**
  - Automate: Upload signed builds to update server after successful CI build
  - Manifest: Generate update manifest with version, checksums, release notes
  - Rollback: Keep previous versions available for downgrade if needed

### Performance & Size Optimization

- [ ] **Analyze and strip unused dependencies from builds**
  - Current: PyInstaller includes all installed packages
  - Problem: Unnecessary bloat (e.g., dev dependencies, unused torch modules)
  - Tool: Use `pipdeptree` to analyze dependency tree
  - Solution: Create minimal production requirements file for PyInstaller

- [ ] **Implement differential updates**
  - Current: Full installer download on every update (~300-500MB)
  - Solution: Binary diff updates (download only changed files, ~10-50MB)
  - Tool: electron-builder's differential update support or custom solution

- [ ] **Add compression optimization for installers**
  - Current: Default compression settings
  - Options: LZMA compression for NSIS (better ratio), 7z for DMG
  - Trade-off: Build time vs installer size (test optimal balance)
  - Target: Reduce installer size by 20-30%

- [ ] **Lazy-load large dependencies in backend**
  - Current: All engines imported at startup (MLX, CUDA, CPU)
  - Problem: Slow startup even if user only needs one engine
  - Solution: Defer imports until first use of specific engine
  - Impact: 2-3x faster startup on user's first launch

## 🔄 Technical Debt (Long-term)

### Code Improvements

- [ ] **Create custom exception classes for launcher**
  - Use `AppBaseException` subclasses instead of generic `ValueError`/`RuntimeError`
  - Follow pattern in `src/core/exceptions.py`

- [ ] **Consolidate path resolution logic**
  - `run.py` has `backend_root_dir()` logic
  - `runtime_paths.py` duplicates some logic
  - Single source of truth needed

- [ ] **Remove unnecessary multiprocessing setup**
  - `force_mp_spawn()` configures torch multiprocessing
  - Erudi doesn't use multiprocessing or torch training currently
  - Adds startup latency for no benefit

- [ ] **Add graceful shutdown handling**
  - `run.py` waits for thread join but doesn't handle signals
  - Add SIGTERM/SIGINT handlers for clean shutdown

- [ ] **Document Windows event loop policy requirement**
  - Sets `WindowsSelectorEventLoopPolicy` for "broader compatibility"
  - Clarify which library requires this setting

- [ ] **Add CI check for backend.spec sync**
  - Verify `backend.spec` stays in sync with requirements
  - Prevent missing dependencies in packaged builds

### Development Experience

- [ ] **Create `scripts/dev/check-backend.sh` helper**
  - Verify backend is running before starting frontend
  - Provide clear error messages if not running

- [ ] **Add data directory migration strategy**
  - Current: one-way copy from bundle to user dir
  - Need sync/update mechanism for app updates

## 🚀 CI/CD & Production Readiness Optimizations

### Requirements Management & Reproducibility

- [ ] **Generate comprehensive requirement freezes for all platforms**
  - Current: Only one freeze file (`v0.1.0-win-cuda-121-freeze.txt`)
  - Missing: Mac Silicon, Mac Intel, Linux variants, Windows CPU/CUDA 11.8
  - Impact: Non-reproducible builds, dependency drift between releases
  - Solution: Generate freeze per platform: `pip freeze > requirements/freezes/v{VERSION}-{PLATFORM}-freeze.txt`
  - CI Action: Auto-generate on release tag, commit to repo
  - Files: `backend/requirements/freezes/` (need 8 files total)

- [ ] **Add pip-compile for deterministic dependency resolution**
  - Current: Manual requirement files with unpinned transitive dependencies
  - Problem: `sentence-transformers==4.1.0` doesn't pin torch, transformers versions
  - Solution: Use `pip-tools` to compile `.in` files → `.txt` with full pinning
  - Benefit: Reproducible builds, faster CI installs, dependency conflict detection
  - Files: Convert all `requirements/meta/*.txt` to `.in` format

- [ ] **Implement dependency vulnerability scanning**
  - Missing: No automated security audits in CI
  - Solution: Add `pip-audit` or `safety` checks in GitHub Actions
  - Fail build on: Critical/High vulnerabilities with available patches
  - Notify on: Medium/Low vulnerabilities via GitHub Security tab
  - Schedule: Run daily on main branch, on all PRs

- [ ] **Add dependency license compliance checks**
  - Current: No license tracking for 50+ dependencies
  - Risk: GPL/AGPL packages may conflict with commercial deployment
  - Solution: Use `pip-licenses` to generate SBOM (Software Bill of Materials)
  - Enforce: Allowlist of acceptable licenses (MIT, Apache-2.0, BSD)
  - Files: Generate `LICENSES.txt` in dist builds

### Build Artifact Management

- [ ] **Create missing PyInstaller spec file with comprehensive config**
  - Critical: `backend.spec` missing from repository (confirmed via search)
  - Current: Build scripts reference non-existent file, builds will fail
  - Must include:
    - All hidden imports (transformers, torch submodules, mlx_lm, bitsandbytes)
    - Data files (data/, logs/, models/, indexes/)
    - Runtime hooks for dynamic imports
    - Platform-specific binaries (MLX, CUDA libs)
    - Exclusions (tests/, docs/, unused modules)
  - Variants: Separate specs for CPU/CUDA/MLX builds to reduce size
  - Files: `backend/backend.spec`, `backend/backend-cpu.spec`, `backend/backend-cuda.spec`

- [ ] **Implement build artifact versioning and tagging**
  - Current: Frontend v1.0.0, Windows tmp dirs v0.1.0 (version drift)
  - Missing: No version in backend, no git commit hash in builds
  - Solution: Single source of truth (`VERSION` file or `pyproject.toml`)
  - Embed: Version + git SHA + build timestamp in binaries
  - Display: Show in UI footer, include in bug reports
  - CI: Auto-bump version on release branches

- [ ] **Add build reproducibility validation**
  - Problem: No guarantee that same source produces identical binaries
  - Impact: Can't verify release integrity, hard to debug user-specific issues
  - Solution: Generate SHA-256 checksums for all build artifacts
  - Publish: Checksums alongside releases for user verification
  - CI: Rebuild same commit, compare hashes to detect non-determinism

- [ ] **Implement artifact size tracking and budgets**
  - Current: No visibility into installer size growth over time
  - Risk: Installers becoming too large (>500MB hurts adoption)
  - Solution: Track artifact sizes in CI, fail if exceeds budget
  - Budgets: DMG < 350MB, Windows NSIS < 400MB, DEB/RPM < 300MB
  - Report: Size trends over releases, identify bloat sources

### CI/CD Pipeline Architecture

- [ ] **Create GitHub Actions workflow for multi-platform builds**
  - Missing: No `.github/workflows/` directory in repo root
  - Required matrices:
    - OS: macOS (12/13/14), Windows (2019/2022), Ubuntu (20.04/22.04)
    - Architecture: x64, arm64 (macOS)
    - Backend: CPU, CUDA 11.8, CUDA 12.1, MLX
  - Jobs: lint → test → build → sign → publish
  - Triggers: Push to main, PR, release tag creation
  - Files: `.github/workflows/build.yml`, `.github/workflows/test.yml`, `.github/workflows/release.yml`

- [ ] **Implement intelligent CI caching strategy**
  - Current: No caching, every build installs 50+ Python packages from scratch
  - Slow: 10-15 minutes per build just for dependencies
  - Solution: Cache by platform + requirements hash
    - Cache `~/.cache/pip` for Python dependencies
    - Cache `node_modules` for npm dependencies
    - Cache PyInstaller `build/` folder for incremental builds
    - Cache HuggingFace model cache (optional, size concern)
  - Invalidation: Hash of requirements files, monthly rotation
  - Expected speedup: 15min → 3-5min per build

- [ ] **Add parallel test execution in CI**
  - Current: Tests run sequentially (backend has 11 test files)
  - Slow: ~5-10 minutes for full test suite
  - Solution: Use pytest-xdist for parallel execution
    - Split by file: `pytest -n auto` (use all CPU cores)
    - Matrix strategy: Run unit tests, integration tests, e2e tests in parallel jobs
  - Optimization: Mark slow tests (model downloads, GPU tests) for separate job
  - Expected speedup: 10min → 2-3min

- [ ] **Implement test result reporting and history tracking**
  - Current: Test failures only visible in CI logs (poor discoverability)
  - Missing: Flaky test detection, performance regression tracking
  - Solution: Use GitHub Actions test reporter or pytest-html
  - Features: Test duration trends, failure rate per test, flaky test warnings
  - Store: Test reports as artifacts, link from PR comments

### Environment & Secret Management

- [ ] **Centralize environment variable configuration**
  - Current: Hardcoded env vars in multiple places
    - `frontend/src/main.js` lines 167-171 (unused)
    - `backend/src/core/config.py` (HF_TOKEN)
    - Setup scripts (INSTALL_TYPE, CI detection)
  - Problem: Inconsistent naming, no validation, scattered documentation
  - Solution: Create `.env.template` with all variables + descriptions
  - Validation: Check required vars on startup, fail fast with clear message
  - Files: `.env.template` (committed), `.env` (gitignored)

- [ ] **Implement secure secret management for CI/CD**
  - Required secrets for production builds:
    - `HF_TOKEN`: HuggingFace API token for downloading gated models
    - `MACOS_CERTIFICATE`: Code signing certificate for macOS
    - `MACOS_CERTIFICATE_PWD`: Certificate password
    - `APPLE_ID`: Apple account for notarization
    - `APPLE_APP_SPECIFIC_PASSWORD`: App-specific password
    - `WINDOWS_CERTIFICATE`: Authenticode certificate for Windows
    - `WINDOWS_CERTIFICATE_PWD`: Certificate password
  - Storage: GitHub Secrets (encrypted at rest)
  - Access: Restrict to protected branches only (main, release/*)
  - Rotation: Document secret rotation procedures, alert on expiry

- [ ] **Add environment-specific configuration validation**
  - Current: No distinction between dev/staging/prod configs
  - Problem: Debug settings leaking to production (verbose logs, open ports)
  - Solution: Environment profiles with validation
    - `config.dev.py`: Debug logs, hot reload, test data
    - `config.staging.py`: Production-like, synthetic data
    - `config.prod.py`: Minimal logs, release mode, real data
  - Enforce: CI checks config matches environment, fail on mismatches

### Quality Gates & Testing

- [ ] **Implement comprehensive pre-commit hooks**
  - Current: No automated checks before commit
  - Problem: Broken code reaches CI, wastes time and resources
  - Hooks: black (format), ruff (lint), mypy (types), pytest (critical tests)
  - Tool: pre-commit framework with `.pre-commit-config.yaml`
  - Fast fail: Run incremental checks on changed files only
  - CI bypass: Allow skipping for hotfixes with `--no-verify` + PR review

- [ ] **Add code coverage tracking with enforcement**
  - Current: pytest-cov installed but no coverage gates
  - Missing: Coverage reports in PRs, trend tracking over time
  - Solution: Use codecov.io or Coveralls integration
  - Thresholds: Fail PR if coverage drops >2%, require 80% minimum
  - Exceptions: Mark low-value areas (e.g., __init__.py, type stubs)
  - Display: Coverage badge in README, detailed reports in PRs

- [ ] **Implement static security analysis (SAST)**
  - Missing: No code security scanning
  - Risks: SQL injection, XSS, hardcoded secrets, insecure crypto
  - Solution: Add bandit (Python) and ESLint security plugin (JavaScript)
  - CI action: Run on all PRs, block merge on high severity issues
  - False positives: Allow suppression with code comments + justification

- [ ] **Add mutation testing for critical paths**
  - Current: Test coverage ≠ test quality (passing tests may not catch bugs)
  - Solution: Use mutmut to mutate code, verify tests fail
  - Focus: Critical domains (conversations, LLM engines, knowledge base)
  - Schedule: Weekly on main branch (slow, don't run on every PR)
  - Report: Mutation score (% of mutants killed), identify weak tests

### Build Performance Optimization

- [ ] **Optimize PyInstaller build for speed**
  - Current: Cold build takes 20-30 minutes
  - Slow steps: Dependency analysis, binary scanning, compression
  - Optimizations:
    - Use `--noconfirm` to skip prompts in CI
    - Cache analysis results with `--upx-dir` (if using UPX)
    - Exclude unnecessary files with `--exclude-module` (e.g., test modules)
    - Parallel builds: Build CPU/CUDA variants simultaneously on separate runners
  - Expected: 30min → 10-15min for full matrix

- [ ] **Implement incremental frontend builds**
  - Current: Electron Forge rebuilds everything on each run
  - Slow: webpack compilation, node_modules scanning
  - Solution: Enable webpack persistent cache
    - Add `cache: { type: 'filesystem' }` to webpack config
    - Cache `.webpack/` folder in CI
    - Clean cache monthly to prevent stale issues
  - Expected: First build 5min, subsequent <1min

- [ ] **Add build parallelization across platforms**
  - Current: Sequential builds (build Mac → Windows → Linux)
  - Solution: GitHub Actions matrix strategy
    - Run all platform builds simultaneously
    - Use max available runners (10 concurrent jobs on GitHub Free)
  - Constraint: macOS runners cost 10x Linux, budget accordingly
  - Expected: 60min sequential → 20min parallel

- [ ] **Implement distributed caching with remote cache**
  - Problem: CI cache not shared between runners or developers
  - Solution: Use build cache service (e.g., sccache for compiled binaries)
  - Benefit: First-time contributors get warm caches
  - Storage: GitHub Packages or AWS S3 with CDN
  - Scope: Share caches within team, isolate by branch for security

### Deployment & Release Automation

- [ ] **Create automated release pipeline**
  - Current: Manual release process (no documentation found)
  - Required steps:
    1. Bump version across all package.json files
    2. Update CHANGELOG.md with release notes
    3. Create git tag and GitHub release
    4. Build all platform variants
    5. Sign binaries (macOS notarization, Windows Authenticode)
    6. Upload artifacts to GitHub Releases
    7. Update website/download page
    8. Publish to update server
  - Automation: GitHub Actions workflow triggered by tag push
  - Files: `.github/workflows/release.yml`

- [ ] **Implement automated changelog generation**
  - Current: No CHANGELOG.md found in repo
  - Problem: Users don't know what changed between versions
  - Solution: Generate from conventional commits or PR labels
  - Format: Keep-a-Changelog compliant with categories (Added, Changed, Fixed, Security)
  - Automation: Update on every release, commit to repo
  - Display: Show in app's "What's New" section

- [ ] **Add smoke tests for release artifacts**
  - Critical: Verify builds before publishing to users
  - Tests:
    - App launches without errors
    - Backend health endpoint responds
    - Database initializes correctly
    - Basic chat completes successfully
    - Model download works (use small test model)
  - Environment: Clean VMs for each platform (no dev tools installed)
  - Automation: Run after build, before publish step
  - Failure action: Block release, alert team

- [ ] **Implement staged rollout with feature flags**
  - Risk: New releases may have critical bugs affecting all users
  - Solution: Gradual rollout with killswitch capability
    - 1% of users get update first (canary)
    - Monitor error rates, crash reports
    - Automatically roll back if thresholds exceeded
    - Gradually increase to 10% → 50% → 100%
  - Infrastructure: Update server with user cohort tracking
  - Backend: Feature flags for risky new features

### Monitoring & Observability

- [ ] **Add build failure notifications**
  - Current: Only visible in GitHub Actions UI
  - Problem: Team may not notice failures for hours
  - Solution: Slack/Discord webhook on build failures
  - Content: Branch name, commit SHA, failing job, error summary, link to logs
  - Recipients: #engineering channel, mention on-call engineer

- [ ] **Implement build performance metrics**
  - Track: Build duration, test duration, artifact sizes, cache hit rates
  - Store: Time series database (InfluxDB) or GitHub API
  - Visualize: Grafana dashboard or GitHub Insights
  - Alerts: Notify if build time >2x baseline, cache hit rate <50%

- [ ] **Add production error tracking**
  - Missing: No way to know if users experiencing crashes/errors
  - Solution: Integrate Sentry or similar error tracking
  - Capture: Uncaught exceptions, backend errors, frontend crashes
  - Enrich: User ID (anonymized), version, OS, hardware specs
  - Privacy: Redact prompts, API keys, personal data

- [ ] **Implement anonymous usage analytics**
  - Goal: Understand feature usage to guide development
  - Metrics: DAU/MAU, feature engagement, model popularity, average session duration
  - Privacy: Fully anonymous (no PII), opt-out mechanism
  - Solution: Use plausible.io or custom lightweight tracker
  - Compliance: GDPR/CCPA compliant, document in privacy policy

### Platform-Specific CI Optimizations

- [ ] **Optimize macOS build for Apple Silicon and Intel**
  - Current: Build script hardcoded to `arm64`
  - Required: Universal binaries (arm64 + x86_64) via lipo
  - Challenge: Some dependencies (MLX) are arm64-only
  - Solution: Separate builds, use automatic architecture selection at runtime
  - Signing: Each architecture must be signed separately before merging
  - Test: Rosetta 2 compatibility on Intel Macs

- [ ] **Add Windows code signing automation**
  - Current: Code signing placeholders in forge config (commented out)
  - Required: Authenticode signing to avoid SmartScreen warnings
  - Certificate: EV certificate required for immediate reputation (or standard + time)
  - Tool: SignTool.exe or electron-builder's built-in signing
  - Automation: Sign both installer (NSIS) and main executable
  - Verification: Check signature after signing, fail if invalid

- [ ] **Implement macOS notarization in CI**
  - Required: Apple notarization for Gatekeeper (macOS 10.15+)
  - Process: Sign → zip → submit to Apple → wait for approval → staple
  - Tool: `xcrun notarytool` or electron-notarize
  - Timeline: 5-15 minutes wait time per build
  - Fallback: Continue on notarization failure for development builds
  - Files: Add `scripts/build/mac/notarize.js`

- [ ] **Add Linux package repository publishing**
  - Current: DEB/RPM builds created but not distributed
  - Solution: Host apt/yum repositories
  - Platforms: Ubuntu PPA, Debian repository, Fedora Copr, AUR (Arch)
  - Automation: Update repos on release, sign packages with GPG key
  - Benefit: Users get updates via system package manager

### Documentation & Developer Experience

- [ ] **Create comprehensive CI/CD documentation**
  - Missing: No docs for build/release process
  - Required sections:
    - Architecture overview (build pipeline flowchart)
    - Local development setup (mirrors CI environment)
    - How to add new platform/variant
    - Troubleshooting common build failures
    - Release checklist (manual + automated steps)
  - Location: `docs/dev/ci-cd.md`

- [ ] **Add CI status badges to README**
  - Show: Build status (passing/failing), test coverage %, latest release version
  - Per-platform: Separate badges for macOS, Windows, Linux
  - Link: Click badge to see detailed CI logs
  - Benefit: Immediate visibility into project health

- [ ] **Implement local CI simulation**
  - Problem: CI failures hard to reproduce locally
  - Solution: Use `act` to run GitHub Actions locally
  - Alternative: Docker Compose file mirroring CI environment
  - Include: Same Python/Node versions, platform-specific tools
  - Files: `docker-compose.ci.yml`, `.actrc`

- [ ] **Create onboarding documentation for new contributors**
  - Current: High barrier to entry (complex build system, 11 setup scripts)
  - Required: Step-by-step guide from git clone to first contribution
  - Include: Dev environment setup, running tests, building locally, submitting PR
  - Optimize: Single command setup where possible
  - Location: `CONTRIBUTING.md`

### Compliance & Legal

- [ ] **Add SBOM generation for supply chain security**
  - Required: Transparency for enterprise customers
  - Generate: CycloneDX or SPDX format SBOM
  - Include: All dependencies (Python, npm, system libraries)
  - Publish: Alongside releases for customer review
  - Tool: `cyclonedx-py` for Python, `@cyclonedx/cyclonedx-npm` for JavaScript

- [ ] **Implement build provenance tracking**
  - Requirement: SLSA Level 2+ for security-conscious users
  - Track: Source commit, builder identity, build commands, artifact hashes
  - Sign: Provenance document with project signing key
  - Verify: Users can verify binary authenticity
  - Tool: SLSA GitHub Actions or in-toto

- [ ] **Add export compliance documentation**
  - Concern: Cryptography export controls (PyTorch contains encryption)
  - Required: Export Control Classification Number (ECCN) determination
  - Document: Cryptography usage, export restrictions by country
  - Disclaimer: Legal notice in README and LICENSE
  - Consult: Legal counsel for export to restricted countries

## 🎨 Frontend Code Quality & Architecture Optimizations

### Code Organization & Architecture

- [ ] **Implement proper project structure with feature-based organization**
  - Current: Flat structure (all pages in `/pages`, all components in `/components`)
  - Problem: Hard to navigate, no clear boundaries between features
  - Solution: Feature-based structure with colocation
    ```
    src/
    ├── features/
    │   ├── models/
    │   │   ├── components/
    │   │   ├── hooks/
    │   │   ├── services/
    │   │   └── pages/
    │   ├── chat/
    │   ├── arena/
    │   └── knowledge-base/
    ├── shared/
    │   ├── components/
    │   ├── hooks/
    │   ├── utils/
    │   └── services/
    ```
  - Benefit: Better maintainability, easier testing, clear ownership

- [ ] **Extract API client into centralized service layer**
  - Current: Raw `fetch()` calls scattered across 50+ locations
  - Issues: No error handling standardization, no retry logic, no request/response interceptors
  - Solution: Create `/services/api/client.js` with axios or custom fetch wrapper
  - Features: Automatic retries, timeout handling, request cancellation, response transformation
  - Example: `apiClient.get('/llms/local')` instead of `fetch(${API_BASE_URL}/llms/local)`
  - Files: New `src/services/api/` directory with modular endpoints

- [ ] **Create custom hooks for data fetching**
  - Current: useEffect + fetch in every component (20+ duplicated patterns)
  - Problem: Repetitive code, no caching, race conditions, memory leaks
  - Solution: Custom hooks like `useLLMs()`, `useConversation(id)`, `useHardwareInfo()`
  - Library: Consider React Query or SWR for advanced caching/revalidation
  - Benefits: Automatic loading states, error handling, deduplication, refetch on focus
  - Files: `src/shared/hooks/api/` directory

- [ ] **Implement proper state management solution**
  - Current: Prop drilling, duplicated state, no single source of truth
  - Problem: Models fetched separately in 5 different pages, conversations state scattered
  - Solution: Zustand or Redux Toolkit for global state
  - Stores: `useModelsStore`, `useConversationsStore`, `useUIStore`
  - Benefit: Centralized state, devtools integration, time-travel debugging
  - Files: `src/stores/` directory

- [ ] **Extract business logic from components into services**
  - Current: 200+ line components with mixed UI/logic (e.g., LandingPage 726 lines)
  - Problem: Untestable, hard to reuse, violates single responsibility
  - Solution: Move logic to services/hooks
    - `parseMetadata()` → `src/utils/modelMetadata.js`
    - API calls → `src/services/modelsService.js`
    - Streaming logic → `src/services/streamingService.js`
  - Components become thin presentational layers
  - Files: All page components need refactoring

### Type Safety & Validation

- [ ] **Add PropTypes or migrate to TypeScript**
  - Critical: Zero PropTypes found, no type checking anywhere
  - Risk: Runtime errors from prop mismatches, hard to refactor
  - Solution (short-term): Add PropTypes to all components
  - Solution (long-term): Migrate to TypeScript (.jsx → .tsx)
  - Priority: Start with shared components (ModelCard, Sidebar, etc.)
  - Files: All 22 components + 6 pages

- [ ] **Implement runtime data validation for API responses**
  - Current: No validation of backend responses
  - Risk: Unexpected data shapes cause crashes (e.g., missing `model.name`)
  - Solution: Use Zod or Yup for schema validation
  - Example: `LLMSchema.parse(apiResponse)` throws if invalid
  - Catch at API boundary, show user-friendly errors
  - Files: `src/schemas/` directory

- [ ] **Add input validation and sanitization**
  - Current: User inputs accepted without validation
  - Risks: Empty submissions, XSS vulnerabilities, malformed data
  - Solution: Validate at component level + backend
  - Use: React Hook Form with validation schema
  - Files: QuestionInput, CustomizePromptModal, all form components

### Error Handling & User Experience

- [ ] **Implement global error boundary**
  - Missing: No error boundary, app crashes go to white screen
  - Solution: Wrap app in `<ErrorBoundary>` with fallback UI
  - Features: Error logging to backend, "Report Bug" button, graceful recovery
  - Library: react-error-boundary
  - File: `src/components/ErrorBoundary.jsx`

- [ ] **Standardize error handling patterns**
  - Current: Inconsistent try/catch, silent failures, no user feedback
  - Found: 20+ different error handling approaches
  - Solution: Centralized error handler
    ```js
    handleApiError(error, {
      fallbackMessage: "Failed to load models",
      toast: true,
      logToBackend: true
    })
    ```
  - Files: `src/utils/errorHandling.js`

- [ ] **Add loading states and skeletons**
  - Current: LoadingScreen on app init, but no loading UI for data fetching
  - Problem: Users see stale data, then sudden updates (jarring)
  - Solution: Skeleton components for all async data
  - Library: Use skeleton screens instead of spinners
  - Files: `src/components/skeletons/` directory

- [ ] **Implement toast notification system**
  - Current: Error/success messages via modals (blocks user)
  - Problem: Intrusive, user must dismiss before continuing
  - Solution: Toast notifications (non-blocking, auto-dismiss)
  - Library: react-hot-toast or sonner
  - Use cases: Model deleted, download complete, API errors
  - File: `src/components/Toast.jsx`

- [ ] **Add retry logic for failed requests**
  - Current: Failed requests just fail (no retry)
  - Problem: Transient network errors permanently fail operations
  - Solution: Automatic retry with exponential backoff
  - Configure: Max retries (3), backoff multiplier (2x), timeout (30s)
  - Implement in: API client layer
  - Files: `src/services/api/client.js`

### Performance Optimization

- [ ] **Implement code splitting and lazy loading**
  - Current: All pages bundled together (large initial bundle)
  - Problem: Users download code for pages they may never visit
  - Solution: Use React.lazy() for route-based splitting
    ```jsx
    const ArenaPage = lazy(() => import('./pages/ArenaPage'))
    ```
  - Expected: 40% reduction in initial bundle size
  - Add: Loading fallback with Suspense
  - Files: App.jsx, routes configuration

- [ ] **Memoize expensive computations**
  - Current: `parseMetadata()` runs on every render
  - Problem: Parsing 50+ models on each state update
  - Solution: Use `useMemo()` for parsed data
  - Also: `useCallback()` for event handlers passed as props
  - Tools: React DevTools Profiler to find hotspots
  - Files: LandingPage, ConversationPage, ArenaPage

- [ ] **Virtualize long lists**
  - Current: Rendering all models/messages in DOM (100+ items)
  - Problem: Slow scrolling, high memory usage
  - Solution: react-window or react-virtualized
  - Use cases: Model list, chat history, conversation list
  - Expected: 10x faster rendering for large lists
  - Files: ModelCollapsibleSection, ChatCollapsibleSection

- [ ] **Optimize re-renders with React.memo**
  - Current: Child components re-render unnecessarily
  - Example: ModelCard re-renders when unrelated state changes
  - Solution: Wrap pure components with React.memo
  - Identify: Use React DevTools "Highlight updates" feature
  - Priority: Frequently rendered components (cards, list items)
  - Files: ModelCard, Sidebar, HeaderBar

- [ ] **Debounce search input**
  - Current: Search triggers re-render on every keystroke
  - Problem: Filtering 100+ models 10 times while typing "pytorch"
  - Solution: Debounce search query (300ms delay)
  - Library: lodash.debounce or custom hook
  - Files: LandingPage search functionality

- [ ] **Implement image lazy loading and optimization**
  - Current: No image optimization found
  - Solution: Use `loading="lazy"` on images
  - Add: WebP format with fallback, responsive images
  - Tool: imagemin for build-time optimization
  - Files: WelcomeModal, any future image assets

### Code Quality & Maintainability

- [ ] **Remove all console.log statements**
  - Found: 40+ console.log statements in production code
  - Problem: Performance overhead, leaked sensitive data, unprofessional
  - Solution: Replace with proper logging
    - Development: Debug library with namespaces
    - Production: Log to backend or analytics service
  - Enforce: ESLint rule `no-console` (error)
  - Files: All pages (ChatPage, TrainingPage, KnowledgeBasePage, etc.)

- [ ] **Add ESLint with strict configuration**
  - Current: No linting, package.json has placeholder `echo \"No linting configured\"`
  - Critical: No code quality enforcement
  - Solution: Install ESLint + airbnb config or Standard
  - Rules: no-unused-vars, no-console, jsx-a11y, react-hooks/exhaustive-deps
  - Add: Pre-commit hook with lint-staged
  - Files: `.eslintrc.json`, update package.json scripts

- [ ] **Add Prettier for consistent formatting**
  - Current: Inconsistent indentation, quote styles, spacing
  - Solution: Add Prettier with consistent config
  - Config: 2-space indent, single quotes, trailing commas
  - Integrate: Format on save, pre-commit hook
  - Files: `.prettierrc.json`, `.prettierignore`

- [ ] **Implement component documentation with Storybook**
  - Missing: No component documentation, hard for new developers
  - Solution: Storybook for component catalog
  - Benefits: Visual testing, isolated development, living documentation
  - Start with: Shared components (ModelCard, GradientBox, etc.)
  - Files: `.storybook/` directory, `*.stories.jsx` files

- [ ] **Add unit tests for components**
  - Critical: Zero tests found (no .test.jsx or .spec.jsx files)
  - Risk: Regressions undetected, refactoring is dangerous
  - Solution: Jest + React Testing Library
  - Coverage target: 80% for components, 90% for utils
  - Priority: Test critical paths (chat, model download, conversations)
  - Files: All components need `*.test.jsx` alongside

- [ ] **Add integration tests for user flows**
  - Missing: No E2E or integration tests
  - Solution: Playwright or Cypress
  - Test scenarios:
    - Download model → chat → create conversation
    - Create knowledge base → attach to model
    - Arena mode with multiple models
  - Run in CI: On every PR and release
  - Files: `tests/e2e/` directory

### Accessibility (a11y)

- [ ] **Add ARIA labels and semantic HTML**
  - Current: Buttons without labels, divs instead of buttons
  - Problem: Unusable for screen readers
  - Solution: Use semantic elements, add aria-label where needed
  - Example: Icon-only buttons need aria-label
  - Tool: axe DevTools to find violations
  - Files: All components with interactive elements

- [ ] **Implement keyboard navigation**
  - Current: No keyboard shortcuts, poor tab order
  - Solution: Add keyboard shortcuts for common actions
    - `Ctrl+K`: Focus search
    - `Ctrl+N`: New conversation
    - `Esc`: Close modals
  - Add: Skip links, focus management
  - Files: App.jsx, modal components

- [ ] **Add focus management for modals**
  - Current: Modals don't trap focus, no return focus
  - Problem: Tab escapes modal, can't close with Escape
  - Solution: Use react-focus-lock or implement focus trap
  - Add: Return focus to trigger element on close
  - Files: All modal components (9 modals found)

- [ ] **Ensure color contrast meets WCAG standards**
  - Current: Gray text on gray backgrounds (low contrast)
  - Problem: Hard to read for users with vision impairments
  - Solution: Check contrast ratios (4.5:1 minimum)
  - Tool: Chrome DevTools Lighthouse, WebAIM contrast checker
  - Files: Tailwind config, CSS overrides

### Security

- [ ] **Implement Content Security Policy**
  - Current: Weak CSP in webpack.renderer.config.js
  - Problem: Allows `unsafe-inline` (XSS risk)
  - Solution: Remove unsafe-inline, use nonces for scripts
  - Add: script-src 'self', connect-src API_BASE_URL only
  - File: `frontend/webpack.renderer.config.js` lines 36-43

- [ ] **Sanitize markdown rendering**
  - Current: MarkdownRenderer may allow XSS via malicious markdown
  - Solution: Configure react-markdown with strict settings
  - Disable: HTML in markdown, dangerous attributes
  - Use: rehype-sanitize plugin
  - File: `src/components/MarkdownRenderer.jsx`

- [ ] **Add rate limiting for API calls**
  - Current: No rate limiting on frontend
  - Risk: User can spam requests (DoS self, backend overload)
  - Solution: Throttle expensive operations
    - Model search: 500ms debounce
    - Message send: Disable button until response
    - Download: One at a time
  - Files: All API calling code

### Developer Experience

- [ ] **Add environment variable validation**
  - Current: Single hardcoded API_BASE_URL
  - Problem: Can't configure for different environments
  - Solution: Use .env files with validation
    - `REACT_APP_API_URL`: Backend URL (required)
    - `REACT_APP_ENV`: dev/staging/prod
    - `REACT_APP_SENTRY_DSN`: Error tracking (optional)
  - Validate: At startup, fail fast if missing
  - Files: `.env.example`, `src/config/env.js`

- [ ] **Add meaningful component and file naming**
  - Current: Inconsistent naming (DatasetCard vs dataset-card)
  - Solution: Establish conventions
    - Components: PascalCase (ModelCard.jsx)
    - Utilities: camelCase (hardwareTransform.js)
    - Constants: UPPER_SNAKE_CASE
  - Document: In CONTRIBUTING.md
  - Refactor: Rename inconsistent files

- [ ] **Create reusable form components**
  - Current: Duplicated form logic across pages
  - Problem: Inconsistent validation, styling, error handling
  - Solution: Create form primitives
    - `<Input>`, `<Select>`, `<TextArea>`, `<Slider>`
    - Built-in validation, error display, labels
  - Use: React Hook Form for state management
  - Files: `src/components/forms/` directory

- [ ] **Add debug mode for development**
  - Missing: No debug tools for developers
  - Solution: Debug panel showing:
    - Current route, active modals, API calls
    - Redux/Zustand state inspector
    - Feature flags toggle
  - Trigger: `Ctrl+Shift+D` or URL param `?debug=true`
  - Only: Development mode
  - File: `src/components/DebugPanel.jsx`

### Refactoring Priorities (High Impact)

- [ ] **Refactor LandingPage (726 lines → <300 lines)**
  - Extract: ModelLibrary, SearchBar, HardwareStatus components
  - Move: API calls to custom hooks (useModels, useHardware)
  - Separate: State management into store
  - Current: Unmaintainable monolith
  - File: `src/pages/LandingPage.jsx`

- [ ] **Refactor ConversationPage (638 lines → <250 lines)**
  - Extract: MessageList, ChatHeader, ChatInput components
  - Move: Streaming logic to service
  - Simplify: Too many useEffect hooks (5+)
  - File: `src/pages/ConversationPage.jsx`

- [ ] **Refactor DownloadModalContext (295 lines)**
  - Problem: Context doing too much (state + UI + API)
  - Split: Separate download state from UI modal
  - Move: Progress tracking to hook
  - File: `src/contexts/DownloadModalContext.jsx`

- [ ] **Consolidate modal components**
  - Current: 9 modal components with duplicated structure
  - Solution: Single `<Modal>` base component
  - Props: title, children, onClose, size
  - Benefit: Consistent behavior, less code
  - Files: All files in `src/components/modals/`

- [ ] **Standardize API response transformations**
  - Current: Inline transformations repeated everywhere
  - Example: `parseMetadata()` duplicated with variations
  - Solution: Single transformation layer in API client
  - Define: DTO (Data Transfer Object) types
  - Files: `src/services/api/transformers.js`

## 📚 Documentation Integration & User Guides

### Frontend Developer Documentation

- [ ] **Add JSDoc documentation to all frontend components**
  - Current: Only 4 files have partial JSDoc (hardwareTransform.js, DragDropArea.jsx, ModelLibrary.jsx)
  - Missing: 18 components, 6 pages, all services without documentation
  - Standard: Google-style JSDoc with @param, @returns, @throws, @example
  - Required sections:
    - Component description and purpose
    - Props documentation with types and defaults
    - Usage examples
    - Related components/hooks
  - Files: All 22 components + 6 pages need comprehensive JSDoc

- [ ] **Create frontend API reference documentation**
  - Missing: No automated frontend docs generation
  - Solution: JSDoc → documentation.js or react-docgen
  - Generate: HTML documentation site from JSDoc comments
  - Include: Components, hooks, utils, services, contexts
  - Integrate: With mkdocs or separate Docusaurus site
  - Files: New `docs/frontend/reference/` directory

- [ ] **Document component props with PropTypes or TypeScript interfaces**
  - Current: Zero PropTypes, no type documentation
  - Solution: Add PropTypes to all components immediately
  - Include: Type, required/optional, default values, description
  - Generate: Auto-documentation from PropTypes
  - Files: All components need PropTypes

- [ ] **Create frontend architecture documentation**
  - Missing: No docs explaining frontend structure
  - Required sections:
    - Project structure and organization
    - State management patterns (contexts, hooks)
    - Routing and navigation flow
    - API communication patterns
    - Component hierarchy and relationships
    - Build and bundle architecture
  - File: `docs/frontend/architecture.md`

- [ ] **Document Electron main process and IPC patterns**
  - Current: Complex main.js (756 lines) with no documentation
  - Required:
    - Backend spawning and lifecycle management
    - IPC channels and event handling
    - Window management and navigation
    - File system operations
    - Error handling and recovery
  - Files: `docs/frontend/electron-main.md`, `docs/frontend/ipc-reference.md`

- [ ] **Add inline code comments for complex logic**
  - Current: Complex algorithms without explanation
  - Examples needing comments:
    - Streaming message assembly (ArenaPage buffering)
    - Metadata parsing logic (LandingPage)
    - Auto-scroll detection (ConversationPage)
    - Download progress polling (DownloadModalContext)
  - Standard: Explain WHY, not WHAT (code shows what)
  - Files: All pages with complex state logic

### Frontend Developer Guides

- [ ] **Create component development guide**
  - Topics:
    - Creating new components (template, location, naming)
    - Component testing strategy
    - Styling with Tailwind conventions
    - Accessibility requirements
    - Performance considerations
  - File: `docs/frontend/guides/component-development.md`

- [ ] **Write state management guide**
  - Current: Ad-hoc state patterns, no documentation
  - Topics:
    - When to use local state vs context
    - Custom hooks for shared state
    - Context best practices
    - Avoiding prop drilling
    - State synchronization with backend
  - File: `docs/frontend/guides/state-management.md`

- [ ] **Document API integration patterns**
  - Topics:
    - Making API requests (fetch patterns)
    - Error handling and retries
    - Loading states and UI feedback
    - Request cancellation
    - Response transformation
    - Streaming responses
  - File: `docs/frontend/guides/api-integration.md`

- [ ] **Create styling and theming guide**
  - Topics:
    - Tailwind utility patterns
    - Color palette and theme variables
    - Responsive design breakpoints
    - Dark mode implementation
    - Component styling conventions
    - Animation patterns
  - File: `docs/frontend/guides/styling-guide.md`

- [ ] **Write testing guide for frontend**
  - Topics:
    - Unit testing components (Jest + RTL)
    - Integration testing (user flows)
    - Mocking API calls
    - Testing async operations
    - Snapshot testing
    - E2E testing with Playwright
  - File: `docs/frontend/guides/testing-guide.md`

### Frontend Build & Launch Documentation

- [ ] **Document frontend build process**
  - Current: No documentation on webpack, Forge, bundling
  - Required:
    - Webpack configuration explained
    - Electron Forge setup and makers
    - Build variants (dev/prod)
    - Asset optimization
    - Code splitting strategy
  - File: `docs/frontend/guides/build-process.md`

- [ ] **Create frontend development setup guide**
  - Topics:
    - Environment setup (Node, npm versions)
    - Installing dependencies
    - Running dev server
    - Hot reload configuration
    - Debugging in VSCode
    - Browser DevTools usage
  - File: `docs/frontend/guides/development-setup.md`

- [ ] **Document frontend launch modes**
  - Topics:
    - Development mode (npm start)
    - Production mode (packaged app)
    - Backend connection configuration
    - Environment variables
    - Troubleshooting startup issues
  - File: `docs/frontend/guides/launch-modes.md`

### MkDocs Integration for Frontend

- [ ] **Add frontend section to mkdocs.yml**
  - Current: Only backend documented in mkdocs
  - Add navigation:
    ```yaml
    - 💻 Frontend:
        - Architecture: frontend/architecture.md
        - Development Setup: frontend/guides/development-setup.md
        - Component Development: frontend/guides/component-development.md
        - API Integration: frontend/guides/api-integration.md
        - State Management: frontend/guides/state-management.md
        - Styling Guide: frontend/guides/styling-guide.md
        - Testing Guide: frontend/guides/testing-guide.md
        - Build Process: frontend/guides/build-process.md
        - Reference:
            - Components: frontend/reference/components.md
            - Hooks: frontend/reference/hooks.md
            - Services: frontend/reference/services.md
            - Utils: frontend/reference/utils.md
    ```
  - File: `mkdocs.yml`

- [ ] **Configure JSDoc plugin for mkdocs**
  - Solution: Use mkdocs-material with custom plugin or markdown-inject
  - Alternative: Generate markdown from JSDoc, include in mkdocs
  - Tool: documentation.js with markdown template
  - Build: Auto-generate on docs build
  - Files: New `scripts/docs/generate-frontend-docs.js`

- [ ] **Add code examples from frontend to docs**
  - Extract: Usage examples from JSDoc
  - Include: Live component examples with code
  - Tool: MDX or markdown-include for code snippets
  - Files: All frontend guide pages

- [ ] **Create component showcase in docs**
  - Purpose: Visual reference for all UI components
  - Include: Screenshots, props table, usage examples
  - Tool: Storybook or custom markdown generator
  - File: `docs/frontend/reference/component-showcase.md`

### Function & Component Tracing

- [ ] **Add call graph documentation**
  - Generate: Component dependency graph
  - Show: Parent-child relationships, data flow
  - Tool: madge or dependency-cruiser
  - Visual: Mermaid diagrams in markdown
  - File: `docs/frontend/architecture/component-graph.md`

- [ ] **Document data flow diagrams**
  - Show: API call → state update → UI render flow
  - Include: Key user interactions (chat, download, KB creation)
  - Format: Mermaid sequence diagrams
  - Files: `docs/frontend/architecture/data-flow-*.md`

- [ ] **Create component API surface documentation**
  - List: All public methods, events, slots for each component
  - Include: Component lifecycle and side effects
  - Format: Auto-generated from JSDoc
  - File: `docs/frontend/reference/component-api.md`

- [ ] **Add hook dependencies and effects documentation**
  - Document: useEffect dependencies and cleanup
  - Trace: State changes and re-render triggers
  - Warning: Common pitfalls (infinite loops, stale closures)
  - File: `docs/frontend/reference/hooks-reference.md`

### Best Practices Documentation

- [ ] **Create frontend code style guide**
  - Topics:
    - Naming conventions (components, files, variables)
    - File organization and imports
    - Component structure patterns
    - Code formatting rules
    - Comment standards
  - Reference: Airbnb React style guide as base
  - File: `docs/frontend/best-practices/code-style.md`

- [ ] **Document performance best practices**
  - Topics:
    - Memoization strategies
    - Code splitting patterns
    - Bundle size optimization
    - Lazy loading techniques
    - Re-render optimization
  - File: `docs/frontend/best-practices/performance.md`

- [ ] **Write accessibility best practices**
  - Topics:
    - Semantic HTML usage
    - ARIA labels and roles
    - Keyboard navigation
    - Screen reader support
    - Color contrast requirements
  - File: `docs/frontend/best-practices/accessibility.md`

- [ ] **Create security best practices**
  - Topics:
    - XSS prevention
    - CSP configuration
    - Input sanitization
    - Secure API communication
    - Dependency security
  - File: `docs/frontend/best-practices/security.md`

## 📖 User Documentation (Non-Technical)

### User Documentation Architecture

- [ ] **Create separate user documentation site**
  - Purpose: End-user guides without code/technical details
  - Structure:
    ```
    docs-user/
    ├── index.md                    # Welcome & overview
    ├── getting-started/
    │   ├── installation.md         # Download & install
    │   ├── first-launch.md         # Initial setup
    │   └── interface-overview.md   # UI walkthrough
    ├── features/
    │   ├── chat.md                 # Chatting with models
    │   ├── models.md               # Managing models
    │   ├── knowledge-base.md       # Creating KB assistants
    │   ├── arena.md                # Comparing models
    │   └── settings.md             # App configuration
    ├── guides/
    │   ├── download-model.md       # Step-by-step model download
    │   ├── create-conversation.md  # Creating conversations
    │   ├── attach-knowledge.md     # Knowledge base attachment
    │   ├── customize-prompts.md    # Prompt customization
    │   └── compare-models.md       # Using arena mode
    ├── troubleshooting/
    │   ├── common-issues.md        # FAQ
    │   ├── performance.md          # Performance tips
    │   └── error-messages.md       # Error explanations
    └── reference/
        ├── system-requirements.md  # Hardware requirements
        ├── keyboard-shortcuts.md   # Shortcuts reference
        └── glossary.md             # Terms explained
    ```

- [ ] **Configure separate MkDocs for user docs**
  - File: `mkdocs-user.yml`
  - Theme: Material with friendly, non-technical tone
  - Features: Search, navigation, no code blocks
  - Deploy: Separate URL (e.g., docs.erudi.app vs dev.erudi.app)
  - Build: `mkdocs build -f mkdocs-user.yml`

### User Guide Content (with Screenshots)

- [ ] **Create installation guide with screenshots**
  - Topics:
    - System requirements check
    - Download from website
    - Installation wizard steps (per OS)
    - First launch and permissions
    - Welcome screen walkthrough
  - Screenshots: Every step with annotations
  - File: `docs-user/getting-started/installation.md`

- [ ] **Write interface overview guide**
  - Topics:
    - Sidebar navigation explained
    - Main sections (Models, Chat, Arena, KB)
    - Top bar and settings
    - Model cards and actions
    - Status indicators
  - Screenshots: Annotated UI elements
  - File: `docs-user/getting-started/interface-overview.md`

- [ ] **Create "Download Your First Model" tutorial**
  - Steps:
    1. Navigate to Models page
    2. Browse model library
    3. Select model (with recommendations)
    4. Download and wait for progress
    5. Model appears in local models
  - Screenshots: Each step with arrows/highlights
  - File: `docs-user/guides/download-model.md`

- [ ] **Write "Start Your First Chat" tutorial**
  - Steps:
    1. Select model from local models
    2. Click chat icon
    3. Type message
    4. Understand response
    5. Continue conversation
  - Screenshots: Full flow with example chat
  - File: `docs-user/guides/start-first-chat.md`

- [ ] **Create knowledge base creation guide**
  - Steps:
    1. Prepare documents (PDF/TXT)
    2. Select model for KB
    3. Upload documents
    4. Name your assistant
    5. Wait for processing
    6. Chat with KB-enhanced model
  - Screenshots: Upload UI, processing status, chat example
  - File: `docs-user/guides/create-knowledge-base.md`

- [ ] **Write arena mode comparison guide**
  - Steps:
    1. Navigate to Arena
    2. Select multiple models
    3. Enter question
    4. Compare responses side-by-side
    5. Analyze differences
  - Screenshots: Multi-panel view, response comparison
  - File: `docs-user/guides/use-arena-mode.md`

- [ ] **Create conversation management guide**
  - Topics:
    - Creating new conversations
    - Accessing conversation history
    - Deleting conversations
    - Customizing conversation settings
    - Temperature/top-p/max-tokens explained (simple)
  - Screenshots: Conversation list, settings modal
  - File: `docs-user/guides/manage-conversations.md`

### Feature Documentation (User-Facing)

- [ ] **Document chat features**
  - Topics:
    - Sending messages
    - Copying responses
    - Starring important messages
    - Markdown formatting in responses
    - Conversation parameters
  - No code: Focus on what users see/do
  - Screenshots: Chat interface, actions, settings
  - File: `docs-user/features/chat.md`

- [ ] **Document model management**
  - Topics:
    - Browsing available models
    - Understanding model sizes and parameters
    - Downloading models
    - Deleting models
    - Model recommendations by use case
  - Screenshots: Model library, download progress, model cards
  - File: `docs-user/features/models.md`

- [ ] **Document knowledge base features**
  - Topics:
    - What is a knowledge base (simple explanation)
    - Supported file types
    - Creating custom assistants
    - How KB improves responses (examples)
    - Managing KB assistants
  - Screenshots: KB creation flow, document upload, enhanced responses
  - File: `docs-user/features/knowledge-base.md`

- [ ] **Document arena mode**
  - Topics:
    - Purpose of model comparison
    - Adding/removing panels
    - Reading parallel responses
    - Understanding model differences
    - Use cases for arena mode
  - Screenshots: Arena interface, multi-panel view
  - File: `docs-user/features/arena.md`

### Troubleshooting & Support

- [ ] **Create common issues FAQ**
  - Questions:
    - App won't start / white screen
    - Model download stuck
    - Chat not responding
    - "Out of memory" errors
    - Slow performance
    - Backend connection failed
  - Answers: Simple steps, no technical jargon
  - File: `docs-user/troubleshooting/common-issues.md`

- [ ] **Write performance optimization guide**
  - Topics:
    - Choosing right model size for hardware
    - Closing unused conversations
    - Managing disk space
    - Recommended model settings
    - Hardware upgrade suggestions
  - File: `docs-user/troubleshooting/performance.md`

- [ ] **Create error message reference**
  - List: All user-facing errors with plain English explanations
  - Include: What caused it, how to fix it
  - Example: "Backend not responding" → restart app
  - File: `docs-user/troubleshooting/error-messages.md`

- [ ] **Write hardware requirements guide**
  - Topics:
    - Minimum vs recommended specs
    - Apple Silicon vs Intel Mac
    - NVIDIA GPU requirements
    - Storage requirements
    - Model size vs RAM calculator
  - File: `docs-user/reference/system-requirements.md`

### Visual Assets for User Docs

- [ ] **Create screenshot library**
  - Capture: All major UI screens at 1920x1080
  - Annotate: Add arrows, labels, highlights
  - Organize: By feature/guide
  - Format: PNG with compression
  - Location: `docs-user/assets/screenshots/`

- [ ] **Add instructional diagrams**
  - Create: Flow diagrams for complex processes
  - Example: Model download flow, KB creation flow
  - Tool: Excalidraw or Figma
  - Style: Match app theme (dark mode)
  - Location: `docs-user/assets/diagrams/`

- [ ] **Create video tutorials**
  - Record: Screen recordings for key workflows
  - Length: 1-3 minutes each
  - Format: MP4, embedded or linked
  - Narration: Optional, text captions included
  - Topics: First chat, KB creation, arena mode
  - Location: YouTube or self-hosted

- [ ] **Design infographics**
  - Topics:
    - Model size comparison chart
    - Hardware compatibility matrix
    - Feature comparison by plan
  - Tool: Canva or Figma
  - Location: `docs-user/assets/infographics/`

### User Documentation Deployment

- [ ] **Set up user docs hosting**
  - Options:
    - GitHub Pages (simple, free)
    - Netlify (auto-deploy from git)
    - Vercel (fast, good analytics)
  - URL: docs.erudi.app or help.erudi.app
  - SSL: Automatic with hosting service

- [ ] **Configure search for user docs**
  - Enable: MkDocs Material search plugin
  - Index: All pages, prioritize guides
  - Features: Instant search, keyboard shortcut
  - Analytics: Track search queries to improve docs

- [ ] **Add feedback mechanism**
  - Include: "Was this helpful?" on each page
  - Tool: Simple form or GitHub Discussions
  - Track: Most/least helpful pages
  - Iterate: Update based on feedback

- [ ] **Create in-app help links**
  - Add: Help icon in app header
  - Link: Direct to relevant doc page
  - Context: Show page based on current screen
  - Example: In Arena → link to arena guide
  - Files: All frontend pages

## Troubleshooting Quick Fixes

### Backend won't start
1. Check logs: `tail -f /tmp/erudi-backend.log`
2. Check JSON events: `./backend/dist/backend/backend` (should emit JSON)
3. Verify executable exists: `ls -la frontend/backend/backend`
4. Check permissions: `chmod +x frontend/backend/backend`
5. Test port availability: `lsof -i :8000`

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
- **Port conflicts**: Backend checks port once, but race conditions possible
- **macOS symlinks**: Runtime bundle modification may affect code signing
- **Test coverage**: Launcher system has zero tests currently (critical gap)

## Success Criteria

The build is ready when:
- ✅ DMG installs successfully
- ✅ App launches without errors
- ✅ Backend starts automatically
- ✅ All features work
- ✅ Data persists
- ✅ No console errors
- ✅ All critical launcher issues resolved
- ✅ Launcher tests pass (unit + integration)
- ✅ JSON event emission works correctly
- ✅ Port conflicts handled gracefully

## Priority Guide

**P0 (Must fix before release):**
- Missing `backend.spec` file
- Port argument mismatch
- Launcher test coverage

**P1 (Should fix before release):**
- Remove unused env vars from `main.js`
- OS-assigned ports implementation
- JSON events logging bridge

**P2 (Nice to have):**
- macOS symlink review
- Custom exception classes
- Path resolution consolidation

**P3 (Future improvements):**
- Multiprocessing cleanup
- Graceful shutdown
- Data migration strategy

---

## Project Infrastructure & Tooling Optimization

> **Context**: Root directory analysis reveals missing critical infrastructure files, incomplete CI/CD setup, outdated README, and missing project configuration files that are standard in professional Python/Node.js projects.

### Category 1: Repository Root Configuration

**Problem**: Missing essential configuration files (pyproject.toml, pytest.ini, .coveragerc, .editorconfig, .gitattributes) that standardize tooling across team and CI/CD.

**Impact**: Inconsistent development environments, no centralized Python project metadata, manual tool configuration duplication.

#### 1.1 Python Project Configuration

- [ ] **Create `backend/pyproject.toml`**
  - **Action**: Centralize all Python tool configs (black, ruff, mypy, pytest, coverage):
    ```toml
    [project]
    name = "erudi"
    version = "1.0.0"
    description = "Local LLM specialization desktop app"
    readme = "README.md"
    requires-python = ">=3.11"
    license = {file = "LICENSE"}
    authors = [
        {name = "Djalil Chikhi"},
        {name = "Rayan Hanader"},
        {name = "Sami Taider"},
        {name = "Youssef Chaouki"},
        {name = "Youssef Laatar"}
    ]
    
    [build-system]
    requires = ["setuptools>=61.0"]
    build-backend = "setuptools.build_meta"
    
    [tool.black]
    line-length = 88
    target-version = ["py311"]
    include = '\.pyi?$'
    
    [tool.ruff]
    line-length = 88
    target-version = "py311"
    select = ["E", "F", "W", "I", "N", "UP", "ANN", "B", "A", "C4", "DTZ", "T10", "ISC", "ICN", "PIE", "PYI", "RSE", "RET", "SIM", "TID", "PTH", "ERA", "PD", "PLE", "PLR", "PLW"]
    ignore = ["ANN101", "ANN102", "PLR0913"]
    
    [tool.mypy]
    python_version = "3.11"
    warn_return_any = true
    warn_unused_configs = true
    disallow_untyped_defs = true
    check_untyped_defs = true
    
    [tool.pytest.ini_options]
    testpaths = ["tests"]
    python_files = ["test_*.py"]
    python_classes = ["Test*"]
    python_functions = ["test_*"]
    addopts = "-v --strict-markers --tb=short --cov=src --cov-report=term-missing --cov-report=html"
    asyncio_mode = "auto"
    markers = [
        "unit: Unit tests",
        "integration: Integration tests",
        "e2e: End-to-end tests",
        "slow: Slow tests (skip by default)",
    ]
    
    [tool.coverage.run]
    source = ["src"]
    omit = ["*/tests/*", "*/venv/*", "*/__pycache__/*"]
    
    [tool.coverage.report]
    exclude_lines = [
        "pragma: no cover",
        "def __repr__",
        "raise AssertionError",
        "raise NotImplementedError",
        "if __name__ == .__main__.:",
        "if TYPE_CHECKING:",
        "class .*\\bProtocol\\):",
        "@(abc\\.)?abstractmethod"
    ]
    ```
  - **Why**: PEP 518 standard. Single source of truth for all Python tooling. Eliminates need for separate `.coveragerc`, `pytest.ini`, `setup.py`.
  - **Expected**: All tools read from `pyproject.toml`. Consistent formatting/linting across dev machines.

- [ ] **Create `.editorconfig`**
  - **Files**: Create `/.editorconfig` (root level)
  - **Action**: Define coding styles for all file types:
    ```ini
    root = true
    
    [*]
    charset = utf-8
    end_of_line = lf
    insert_final_newline = true
    trim_trailing_whitespace = true
    
    [*.{py,pyi}]
    indent_style = space
    indent_size = 4
    max_line_length = 88
    
    [*.{js,jsx,json,yml,yaml}]
    indent_style = space
    indent_size = 2
    
    [*.md]
    trim_trailing_whitespace = false
    
    [Makefile]
    indent_style = tab
    ```
  - **Why**: Ensures consistent formatting across IDEs (VSCode, PyCharm, etc.). Prevents spaces/tabs conflicts.
  - **Expected**: All team members get same indentation/line endings.

- [ ] **Create `.gitattributes`**
  - **Files**: Create `/.gitattributes`
  - **Action**: Normalize line endings and diff handling:
    ```gitattributes
    * text=auto
    
    *.py text eol=lf
    *.js text eol=lf
    *.jsx text eol=lf
    *.json text eol=lf
    *.md text eol=lf
    *.sh text eol=lf
    *.yml text eol=lf
    
    *.bat text eol=crlf
    *.ps1 text eol=crlf
    
    *.png binary
    *.jpg binary
    *.icns binary
    *.dmg binary
    ```
  - **Why**: Prevents cross-platform line ending issues (CRLF vs LF). Essential for Mac/Windows/Linux development.
  - **Expected**: Git handles line endings correctly on all platforms.

- [ ] **Improve `.gitignore`**
  - **Files**: `/.gitignore`
  - **Action**: Add missing entries:
    ```gitignore
    # Add to existing .gitignore:
    
    # Test coverage
    htmlcov/
    .coverage
    .coverage.*
    coverage.xml
    *.cover
    
    # Frontend testing
    frontend/coverage/
    frontend/.nyc_output/
    
    # IDEs
    .idea/
    *.swp
    *.swo
    *~
    
    # OS
    .DS_Store
    Thumbs.db
    desktop.ini
    
    # Build artifacts
    *.dmg
    *.exe
    *.app
    *.deb
    *.rpm
    
    # Secrets
    .env
    .env.*
    !.env.example
    secrets.py
    
    # Node
    node_modules/
    npm-debug.log*
    yarn-debug.log*
    yarn-error.log*
    
    # Python
    *.pyc
    __pycache__/
    *.egg-info/
    dist/
    build/
    .pytest_cache/
    .mypy_cache/
    .ruff_cache/
    
    # Logs
    *.log
    logs/
    
    # Temporary
    tmp/
    temp/
    *.tmp
    ```
  - **Why**: Current `.gitignore` incomplete (missing coverage, IDEs, secrets). Prevents accidental commits.
  - **Expected**: No sensitive files or build artifacts committed.

#### 1.2 README Modernization

- [ ] **Rewrite `README.md` to professional standard**
  - **Files**: `/README.md`
  - **Issues**:
    - Empty first 6 lines
    - Mixed languages (French/English)
    - References old project name "SMARTER"
    - No project description, features, architecture
    - Setup instructions scattered and incomplete
    - No badges, screenshots, or contribution guide
  - **Action**: Complete rewrite following best practices:
    ```markdown
    <div align="center">
      <img src="frontend/src/img/logoerudifinal.png" alt="Erudi Logo" width="200"/>
      <h1>Erudi</h1>
      <p><strong>Local LLM Specialization — Offline, Private, Powerful</strong></p>
      
      [![License](https://img.shields.io/badge/license-SEE%20LICENSE-blue)](LICENSE)
      [![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
      [![Node](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
      [![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)](https://github.com/djaxchi/erudi)
    </div>
    
    ---
    
    ## 🧠 What is Erudi?
    
    Erudi is a **desktop application** for running and fine-tuning large language models (LLMs) **locally** on your machine. No cloud. No API keys. Just you and your data.
    
    - **Multi-Engine Support**: Apple Silicon (MLX), NVIDIA CUDA, or CPU
    - **Fine-Tuning Made Easy**: Upload documents, train custom models—no code
    - **Private by Design**: All data stays on your device
    - **Arena Mode**: Compare multiple models side-by-side
    - **RAG Knowledge Base**: Chat with your documents
    
    ---
    
    ## ✨ Features
    
    - 🚀 **One-Click Model Downloads** from Hugging Face
    - 💬 **Conversational UI** with streaming responses
    - 📚 **Knowledge Base (RAG)** for document Q&A
    - 🔧 **Custom Fine-Tuning** with your own data
    - ⚖️ **Arena Mode** to benchmark models
    - 🔒 **100% Offline** operation
    - 🖥️ **Cross-Platform** (macOS, Windows, Linux)
    
    ---
    
    ## 🎯 Quick Start
    
    ### Prerequisites
    - **Python 3.11+**
    - **Node.js 18+**
    - **Git**
    
    ### Installation
    
    #### macOS (Apple Silicon - M1/M2/M3+)
    ```bash
    git clone https://github.com/djaxchi/erudi.git
    cd erudi
    bash ./scripts/dev/backend/setup-mac-silicon.sh
    ```
    
    #### macOS (Intel)
    ```bash
    bash ./scripts/dev/backend/setup-mac-intel.sh
    ```
    
    #### Windows (CUDA 12.1)
    ```powershell
    .\scripts\dev\backend\setup-win-cuda-121.ps1
    ```
    
    #### Linux (CUDA 12.1)
    ```bash
    bash ./scripts/dev/backend/setup-linux-cuda-121.sh
    ```
    
    > See [docs/usage.md](docs/usage.md) for all platform options.
    
    ### Running the App
    
    ```bash
    # Terminal 1: Start backend
    cd backend
    source venv/bin/activate  # or `venv\Scripts\activate` on Windows
    python run.py
    
    # Terminal 2: Start frontend
    cd frontend
    npm install
    npm start
    ```
    
    ---
    
    ## 📖 Documentation
    
    - **[Architecture](docs/architecture.md)** - System design and components
    - **[User Guide](docs/usage.md)** - Installation and usage
    - **[API Reference](docs/reference/)** - Backend API documentation
    - **[Build Guide](BUILD.md)** - Creating distributable packages
    
    ---
    
    ## 🏗️ Architecture
    
    - **Backend**: FastAPI + SQLAlchemy + FAISS
    - **Frontend**: Electron + React + Tailwind CSS
    - **Engines**: MLX (Apple Silicon), llama.cpp (CUDA/CPU)
    - **Database**: SQLite with WAL mode
    
    ```
    erudi/
    ├── backend/       # FastAPI backend
    │   ├── src/       # Source code
    │   ├── tests/     # Test suite
    │   └── requirements/  # Multi-platform dependencies
    ├── frontend/      # Electron + React app
    │   └── src/       # React components
    └── docs/          # Documentation (MkDocs)
    ```
    
    ---
    
    ## 🧪 Development
    
    ### Backend Tests
    ```bash
    cd backend
    pytest                    # Run all tests
    pytest --cov=src          # With coverage
    pytest tests/test_engines.py  # Specific file
    ```
    
    ### Code Quality
    ```bash
    black .                   # Format code
    ruff check .              # Lint
    mypy src/                 # Type check
    ```
    
    ### Frontend
    ```bash
    cd frontend
    npm test                  # Run tests (when implemented)
    npm run lint              # Lint code
    ```
    
    ---
    
    ## 📦 Building for Distribution
    
    See [BUILD.md](BUILD.md) for complete build instructions.
    
    ```bash
    # Quick build (macOS)
    ./scripts/build/mac/build-full-mac-silicon.sh
    
    # Quick build (Windows)
    npm run build:full
    ```
    
    ---
    
    ## 🤝 Contributing
    
    We welcome contributions! Please:
    
    1. Fork the repository
    2. Create a feature branch (`git checkout -b feature/amazing-feature`)
    3. Commit your changes (`git commit -m 'Add amazing feature'`)
    4. Push to the branch (`git push origin feature/amazing-feature`)
    5. Open a Pull Request
    
    See [.github/copilot-instructions.md](.github/copilot-instructions.md) for coding standards.
    
    ---
    
    ## 📄 License
    
    See [LICENSE](LICENSE) file for details.
    
    ---
    
    ## 👥 Authors
    
    - **Djalil Chikhi**
    - **Rayan Hanader**
    - **Sami Taider**
    - **Youssef Chaouki**
    - **Youssef Laatar**
    
    ---
    
    ## 🙏 Acknowledgments
    
    - [llama.cpp](https://github.com/ggerganov/llama.cpp) for GGUF model support
    - [MLX](https://github.com/ml-explore/mlx) for Apple Silicon acceleration
    - [FastAPI](https://fastapi.tiangolo.com/) for the backend framework
    - [Electron](https://www.electronjs.org/) for the desktop app framework
    ```
  - **Why**: Professional README is project's first impression. Current README unprofessional (French, old name, empty lines).
  - **Expected**: Clear project introduction, easy onboarding, professional appearance.

---

### Category 2: CI/CD Infrastructure (GitHub Actions)

**Problem**: No CI/CD workflows found in `.github/workflows/`. No automated testing, linting, or builds on push/PR.

**Impact**: Manual testing before every merge. No quality gates. Broken code can be merged.

#### 2.1 Backend CI Workflow

- [ ] **Create `.github/workflows/backend-ci.yml`**
  - **Action**: Automated backend testing pipeline:
    ```yaml
    name: Backend CI
    
    on:
      push:
        branches: [main, multi-backends-same-branch]
        paths:
          - 'backend/**'
          - '.github/workflows/backend-ci.yml'
      pull_request:
        branches: [main, multi-backends-same-branch]
        paths:
          - 'backend/**'
    
    jobs:
      lint:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - name: Install dependencies
            run: |
              cd backend
              pip install black ruff mypy
          - name: Black check
            run: cd backend && black --check .
          - name: Ruff lint
            run: cd backend && ruff check .
          - name: MyPy type check
            run: cd backend && mypy src/
      
      test:
        runs-on: ${{ matrix.os }}
        strategy:
          matrix:
            os: [ubuntu-latest, macos-latest]
            python-version: ['3.11', '3.12']
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: ${{ matrix.python-version }}
          - name: Install dependencies
            run: |
              cd backend
              pip install -r requirements/entrypoints/dev/linux-cpu.txt
          - name: Run tests
            run: |
              cd backend
              pytest --cov=src --cov-report=xml --cov-report=term
          - name: Upload coverage
            uses: codecov/codecov-action@v4
            with:
              file: ./backend/coverage.xml
              flags: backend
    ```
  - **Why**: No automated testing = manual QA for every PR. CI catches issues before merge.
  - **Expected**: All PRs run tests + linting. Coverage tracked.

#### 2.2 Frontend CI Workflow

- [ ] **Create `.github/workflows/frontend-ci.yml`**
  - **Action**: Automated frontend testing pipeline:
    ```yaml
    name: Frontend CI
    
    on:
      push:
        branches: [main, multi-backends-same-branch]
        paths:
          - 'frontend/**'
          - '.github/workflows/frontend-ci.yml'
      pull_request:
        branches: [main, multi-backends-same-branch]
        paths:
          - 'frontend/**'
    
    jobs:
      lint:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-node@v4
            with:
              node-version: '18'
          - name: Install dependencies
            run: cd frontend && npm ci
          - name: ESLint
            run: cd frontend && npm run lint
      
      test:
        runs-on: ${{ matrix.os }}
        strategy:
          matrix:
            os: [ubuntu-latest, macos-latest, windows-latest]
            node-version: ['18', '20']
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-node@v4
            with:
              node-version: ${{ matrix.node-version }}
          - name: Install dependencies
            run: cd frontend && npm ci
          - name: Run tests
            run: cd frontend && npm test -- --ci --coverage --maxWorkers=2
          - name: Upload coverage
            uses: codecov/codecov-action@v4
            with:
              file: ./frontend/coverage/coverage-final.json
              flags: frontend
    ```
  - **Why**: Frontend has zero tests currently. Prepares for test suite implementation.
  - **Expected**: CI ready when tests added.

#### 2.3 Build Verification Workflow

- [ ] **Create `.github/workflows/build-check.yml`**
  - **Action**: Verify builds don't break:
    ```yaml
    name: Build Check
    
    on:
      push:
        branches: [main]
      pull_request:
        branches: [main]
    
    jobs:
      backend-build:
        runs-on: ${{ matrix.os }}
        strategy:
          matrix:
            os: [ubuntu-latest, macos-latest]
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - name: Install PyInstaller
            run: pip install pyinstaller
          - name: Test backend.spec exists
            run: test -f backend/backend.spec || echo "::error::backend.spec missing"
      
      frontend-package:
        runs-on: macos-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-node@v4
            with:
              node-version: '18'
          - name: Install dependencies
            run: cd frontend && npm ci
          - name: Package (no DMG)
            run: cd frontend && npm run package
    ```
  - **Why**: Build breakages detected early. Ensures `backend.spec` exists.
  - **Expected**: PRs that break builds are blocked.

#### 2.4 Documentation Build Workflow

- [ ] **Create `.github/workflows/docs-build.yml`**
  - **Action**: Build and deploy MkDocs:
    ```yaml
    name: Build Docs
    
    on:
      push:
        branches: [main]
        paths:
          - 'docs/**'
          - 'mkdocs.yml'
          - '.github/workflows/docs-build.yml'
    
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - name: Install MkDocs
            run: pip install mkdocs-material mkdocstrings[python]
          - name: Build docs
            run: mkdocs build --strict
          - name: Deploy to GitHub Pages
            if: github.ref == 'refs/heads/main'
            run: mkdocs gh-deploy --force
    ```
  - **Why**: Docs automatically deployed on merge. Broken docs detected in CI.
  - **Expected**: https://djaxchi.github.io/erudi/ hosts docs.

#### 2.5 Dependency Security Scanning

- [ ] **Create `.github/workflows/security-scan.yml`**
  - **Action**: Scan for vulnerabilities:
    ```yaml
    name: Security Scan
    
    on:
      schedule:
        - cron: '0 0 * * 0'  # Weekly
      workflow_dispatch:
    
    jobs:
      python-security:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - name: Install safety
            run: pip install safety
          - name: Scan Python deps
            run: |
              cd backend
              safety check -r requirements/entrypoints/dev/linux-cpu.txt
      
      node-security:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-node@v4
            with:
              node-version: '18'
          - name: NPM audit
            run: cd frontend && npm audit --audit-level=high
    ```
  - **Why**: Detect vulnerable dependencies before they're exploited.
  - **Expected**: Weekly security reports. Alerts on critical CVEs.

---

### Category 3: Development Experience Improvements

**Problem**: No development convenience tools (Makefile, task runner, unified commands). Developers must memorize multiple commands for different platforms.

**Impact**: Slow onboarding, command mistakes, time wasted looking up commands.

#### 3.1 Makefile for Common Tasks

- [ ] **Create root `Makefile`**
  - **Files**: `/Makefile`
  - **Action**: Unified command interface:
    ```makefile
    .PHONY: help install test lint format clean build dev
    
    help:  ## Show this help
    	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
    
    install:  ## Install all dependencies
    	cd backend && pip install -r requirements/entrypoints/dev/mac-silicon.txt
    	cd frontend && npm install
    
    test:  ## Run all tests
    	cd backend && pytest
    	cd frontend && npm test
    
    test-cov:  ## Run tests with coverage
    	cd backend && pytest --cov=src --cov-report=html
    	cd frontend && npm run test:coverage
    
    lint:  ## Run all linters
    	cd backend && black --check . && ruff check . && mypy src/
    	cd frontend && npm run lint
    
    format:  ## Auto-format code
    	cd backend && black .
    	cd frontend && npm run format
    
    clean:  ## Clean build artifacts
    	rm -rf backend/dist backend/build backend/.pytest_cache backend/htmlcov
    	rm -rf frontend/out frontend/dist frontend/.webpack
    	find . -type d -name __pycache__ -exec rm -rf {} +
    	find . -type d -name .ruff_cache -exec rm -rf {} +
    
    dev:  ## Start dev servers (requires 2 terminals)
    	@echo "Terminal 1: make dev-backend"
    	@echo "Terminal 2: make dev-frontend"
    
    dev-backend:  ## Start backend dev server
    	cd backend && source venv/bin/activate && python run.py
    
    dev-frontend:  ## Start frontend dev server
    	cd frontend && npm start
    
    build:  ## Build for production
    	cd backend && pyinstaller backend.spec
    	cd frontend && npm run make
    
    docs:  ## Serve docs locally
    	mkdocs serve
    
    docs-build:  ## Build docs
    	mkdocs build
    ```
  - **Why**: Developers type `make test` instead of memorizing platform-specific commands.
  - **Expected**: Faster development, consistent commands across team.

#### 3.2 Pre-commit Hooks

- [ ] **Install pre-commit framework**
  - **Files**: Create `.pre-commit-config.yaml`
  - **Action**: Auto-run checks before commit:
    ```yaml
    repos:
      - repo: https://github.com/pre-commit/pre-commit-hooks
        rev: v4.5.0
        hooks:
          - id: trailing-whitespace
          - id: end-of-file-fixer
          - id: check-yaml
          - id: check-json
          - id: check-added-large-files
          - id: check-merge-conflict
          - id: mixed-line-ending
      
      - repo: https://github.com/psf/black
        rev: 24.10.0
        hooks:
          - id: black
            files: ^backend/
      
      - repo: https://github.com/astral-sh/ruff-pre-commit
        rev: v0.8.4
        hooks:
          - id: ruff
            args: [--fix]
            files: ^backend/
      
      - repo: https://github.com/pre-commit/mirrors-mypy
        rev: v1.13.0
        hooks:
          - id: mypy
            files: ^backend/src/
            additional_dependencies: [types-all]
    ```
  - **Install**: `pip install pre-commit && pre-commit install`
  - **Why**: Catch linting/formatting issues before commit, not in CI.
  - **Expected**: Commits automatically formatted and linted.

#### 3.3 Development Environment Validation

- [ ] **Enhance `setup-check.sh`**
  - **Files**: `/setup-check.sh`
  - **Action**: Add checks for:
    - Python version (3.11+)
    - Node.js version (18+)
    - Virtual environment activated
    - Dependencies installed (pip list, npm list)
    - Database file exists and migrated
    - Port 8000 available
    - Git hooks installed
    - Build tools (cmake, PyInstaller)
  - **Why**: Current `setup-check.sh` only checks build artifacts. Should validate full dev environment.
  - **Expected**: One command verifies entire setup.

---

### Category 4: Code Quality Gaps

**Problem**: Analysis revealed 30+ `except Exception` blocks (overly broad), 4 TODO comments in backend, 40+ console.log in frontend, no consistent error handling.

**Impact**: Silent failures, difficult debugging, technical debt accumulates.

#### 4.1 Exception Handling Audit

- [ ] **Replace broad `except Exception` with specific exceptions**
  - **Files**: All backend files with `except Exception` (30+ occurrences found)
  - **Action**: For each broad exception:
    - Identify specific exception types (FileNotFoundError, ValueError, etc.)
    - Replace with specific catches or create custom exceptions
    - Add structured logging with context
  - **Example**:
    ```python
    # Before:
    try:
        result = do_something()
    except Exception as e:
        logger.error(f"Error: {e}")
    
    # After:
    try:
        result = do_something()
    except FileNotFoundError as e:
        raise ModelFileNotFoundError(f"Model file missing: {e.filename}") from e
    except ValueError as e:
        raise InvalidModelConfigError(f"Invalid config: {e}") from e
    ```
  - **Why**: Broad `except Exception` catches unexpected errors silently. Specific exceptions = better debugging.
  - **Expected**: All exceptions have specific handlers. No silent failures.

- [ ] **Create custom exception hierarchy**
  - **Files**: `backend/src/core/exceptions.py`
  - **Action**: Add missing domain-specific exceptions:
    ```python
    # Add to existing file:
    
    class ModelFileNotFoundError(AppBaseException):
        """Model file not found on disk."""
        def __init__(self, message: str):
            super().__init__(
                status_code=404,
                error_code="MODEL_FILE_NOT_FOUND",
                message=message
            )
    
    class InvalidModelConfigError(AppBaseException):
        """Model configuration invalid or malformed."""
        def __init__(self, message: str):
            super().__init__(
                status_code=400,
                error_code="INVALID_MODEL_CONFIG",
                message=message
            )
    
    class EngineInitializationError(AppBaseException):
        """Engine failed to initialize."""
        def __init__(self, engine_type: str, message: str):
            super().__init__(
                status_code=500,
                error_code="ENGINE_INIT_FAILED",
                message=f"{engine_type} initialization failed: {message}"
            )
    
    class InsufficientResourcesError(AppBaseException):
        """System lacks resources for operation."""
        def __init__(self, resource: str, required: str, available: str):
            super().__init__(
                status_code=507,
                error_code="INSUFFICIENT_RESOURCES",
                message=f"Insufficient {resource}: need {required}, have {available}"
            )
    ```
  - **Why**: Current exceptions.py has base classes but few specific exceptions. Custom exceptions improve error messages.
  - **Expected**: All error cases have descriptive custom exceptions.

#### 4.2 TODO/FIXME Resolution

- [ ] **Resolve or document all TODO comments**
  - **Files**: Backend files with TODO (4+ found)
  - **Locations**:
    - `backend/src/domains/conversations/utils/context.py:97` - Implement summarization
    - `backend/src/domains/training/endpoints.py:37,57` - Training engine integration
    - `backend/src/utils/file_processor.py:595` - File processing TODO
  - **Action**: For each TODO:
    - Create GitHub issue if work planned
    - Implement immediately if simple
    - Remove if obsolete
    - Add ticket number if long-term
  - **Why**: TODOs are tech debt. Must be tracked or resolved.
  - **Expected**: Zero untracked TODOs.

#### 4.3 Frontend Error Handling Standardization

- [ ] **Replace generic `catch (e)` with typed errors**
  - **Files**: Frontend files with `catch (e)` (7 occurrences found)
  - **Action**: Create error utility:
    ```javascript
    // frontend/src/utils/errorHandler.js
    export class APIError extends Error {
      constructor(status, code, message) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.code = code;
      }
    }
    
    export class NetworkError extends Error {
      constructor(message) {
        super(message);
        this.name = 'NetworkError';
      }
    }
    
    export function handleAPIError(error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new NetworkError('Cannot connect to backend. Is it running?');
      }
      if (error.response) {
        throw new APIError(
          error.response.status,
          error.response.data?.error_code,
          error.response.data?.message || 'API request failed'
        );
      }
      throw error;
    }
    ```
  - **Why**: Generic `catch (e)` doesn't differentiate network errors from API errors. Users see unhelpful messages.
  - **Expected**: All errors categorized and user-friendly.

---

### Category 5: Missing Build Infrastructure

**Problem**: Build scripts exist but are incomplete. Missing proper versioning, signing documentation, and artifact management.

**Impact**: No reproducible builds. Distribution packages lack version tracking.

**Note**: See Category 1.1 for `backend.spec` creation (lines 2285-2339).

#### 5.1 Build Artifact Versioning

- [ ] **Add version management to builds**
  - **Files**: `backend/src/core/config.py`, `frontend/package.json`
  - **Action**: 
    - Add `VERSION = "1.0.0"` to backend config
    - Update `forge.config.js` to read version from package.json
    - Create `scripts/bump-version.sh` to update all version strings
  - **Why**: No version tracking = can't identify which build users have.
  - **Expected**: All builds tagged with version number.

#### 5.3 Build Artifact Signing

- [ ] **Document code signing for all platforms**
  - **Files**: Create `docs/guides/code-signing.md`
  - **Content**:
    - macOS: Developer ID cert + notarization (existing in NOTARIZATION.md)
    - Windows: Authenticode signing with signtool.exe
    - Linux: GPG signing for .deb/.rpm packages
  - **Why**: Unsigned apps trigger security warnings. Professional distribution requires signing.
  - **Expected**: All distributables signed and verified.

---

## Summary: Infrastructure Optimization Impact

**Current State:**
- ❌ No `pyproject.toml` (Python tools not centralized)
- ❌ No `.editorconfig` (inconsistent formatting)
- ❌ No CI/CD workflows (manual testing only)
- ❌ README unprofessional (French, outdated, empty lines)
- ❌ No `backend.spec` (build blocker)
- ❌ No Makefile (command inconsistency)
- ❌ 30+ broad `except Exception` blocks
- ❌ 4+ untracked TODOs
- ❌ No pre-commit hooks
- ❌ No dependency security scanning

**After Implementation:**
- ✅ Professional Python project structure (pyproject.toml)
- ✅ Consistent code formatting (editorconfig, pre-commit)
- ✅ Automated CI/CD (backend + frontend + docs + security)
- ✅ Professional README with badges, screenshots, clear setup
- ✅ Complete build infrastructure (backend.spec, versioning, signing)
- ✅ Developer convenience (Makefile, enhanced setup-check.sh)
- ✅ Specific exception handling (no broad catches)
- ✅ All TODOs resolved or tracked
- ✅ Security scanning (weekly CVE checks)

**Expected Outcomes:**
- 70%+ faster onboarding (clear README + Makefile)
- Zero merge breakages (CI quality gates)
- 50%+ faster debugging (specific exceptions)
- Professional project appearance (badges, docs, signing)
- Builds work reliably (backend.spec complete)
- Consistent code quality (pre-commit hooks)

**Estimated Effort:**
- Configuration files (pyproject.toml, .editorconfig, etc.): 2-3 hours
- CI/CD workflows (5 workflows): 6-8 hours
- README rewrite: 2-3 hours
- Exception handling audit: 10-12 hours
- Build infrastructure (backend.spec, etc.): 4-6 hours
- Developer tools (Makefile, pre-commit): 3-4 hours
- **Total: 27-36 hours** for complete infrastructure modernization

**Priority:**
- **P0** (Blocking): backend.spec, CI/CD backend tests
- **P1** (High): README, pyproject.toml, exception handling
- **P2** (Medium): CI/CD frontend, Makefile, pre-commit
- **P3** (Low): Security scanning, code signing docs

---

## Frontend Testing Infrastructure Optimization

> **Context**: Frontend has **zero test coverage** (no test files, no testing framework, no test scripts). Current state: 22 components + 6 pages + 2 contexts + services/utils with complex state management, async operations, and Electron IPC—all untested.

### Category 1: Testing Framework Setup

**Problem**: No testing infrastructure exists. `package.json` has no test scripts, dependencies, or configuration.

**Impact**: Unable to write or run tests. No quality gates for code changes. Bugs discovered only in production.

#### 1.1 Install Core Testing Dependencies

- [ ] **Install Jest + React Testing Library**
  - **Files**: `frontend/package.json`
  - **Action**: Add dependencies:
    ```json
    "devDependencies": {
      "@testing-library/react": "^14.1.2",
      "@testing-library/jest-dom": "^6.1.5",
      "@testing-library/user-event": "^14.5.1",
      "jest": "^29.7.0",
      "jest-environment-jsdom": "^29.7.0",
      "@babel/preset-env": "^7.23.5"
    }
    ```
  - **Why**: Jest = standard React testing framework. React Testing Library = best practice for testing React components (official recommendation).
  - **Expected**: Foundation for all frontend testing.

- [ ] **Create Jest configuration file**
  - **Files**: Create `frontend/jest.config.js`
  - **Action**: Configure Jest for React + webpack:
    ```javascript
    module.exports = {
      testEnvironment: 'jsdom',
      setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
      moduleNameMapper: {
        '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
        '\\.(jpg|jpeg|png|gif|svg)$': '<rootDir>/__mocks__/fileMock.js'
      },
      transform: {
        '^.+\\.(js|jsx)$': ['babel-jest', { configFile: './.babelrc.test.js' }]
      },
      testMatch: ['**/__tests__/**/*.[jt]s?(x)', '**/?(*.)+(spec|test).[jt]s?(x)'],
      collectCoverageFrom: [
        'src/**/*.{js,jsx}',
        '!src/index.jsx',
        '!src/main.js',
        '!src/**/*.stories.{js,jsx}',
        '!src/**/__tests__/**'
      ],
      coverageThresholds: {
        global: {
          branches: 70,
          functions: 70,
          lines: 70,
          statements: 70
        }
      }
    };
    ```
  - **Why**: Jest needs configuration for webpack, CSS imports, image mocking, and Babel transforms.
  - **Expected**: Jest can parse JSX and handle frontend imports.

- [ ] **Create test setup file**
  - **Files**: Create `frontend/src/setupTests.js`
  - **Action**: Global test configuration:
    ```javascript
    import '@testing-library/jest-dom';
    
    // Mock window.electron API
    global.window.electron = {
      openDirectory: jest.fn(),
      getFilePath: jest.fn((file) => file.path || file.name)
    };
    
    // Mock window.electronAPI
    global.window.electronAPI = {
      openDataFolder: jest.fn(),
      clearAllData: jest.fn()
    };
    
    // Mock fetch globally
    global.fetch = jest.fn();
    
    // Suppress console errors in tests (optional)
    global.console.error = jest.fn();
    ```
  - **Why**: Electron APIs (`window.electron`) used in 3+ components will crash tests without mocks.
  - **Expected**: Tests can render components using Electron APIs without errors.

- [ ] **Create Babel test configuration**
  - **Files**: Create `frontend/.babelrc.test.js`
  - **Action**:
    ```javascript
    module.exports = {
      presets: [
        ['@babel/preset-env', { targets: { node: 'current' } }],
        ['@babel/preset-react', { runtime: 'automatic' }]
      ]
    };
    ```
  - **Why**: Jest runs in Node.js, needs Babel to transform JSX and modern JS.
  - **Expected**: Test files can use JSX syntax and ES6+ features.

- [ ] **Create file mocks for assets**
  - **Files**: Create `frontend/__mocks__/fileMock.js`
  - **Action**:
    ```javascript
    module.exports = 'test-file-stub';
    ```
  - **Why**: Image imports (e.g., `logoErudi` in LandingPage.jsx) cause Jest to crash.
  - **Expected**: Tests can import components with image assets.

- [ ] **Add test scripts to package.json**
  - **Files**: `frontend/package.json`
  - **Action**: Add to `"scripts"`:
    ```json
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "test:ci": "jest --ci --coverage --maxWorkers=2"
    ```
  - **Why**: Need commands to run tests in development and CI/CD.
  - **Expected**: `npm test` runs test suite.

---

### Category 2: Component Testing (Unit Tests)

**Problem**: 22 components with complex UI logic, state management, and user interactions—all untested. No PropTypes or type validation.

**Impact**: UI regressions go unnoticed. Refactoring is risky. Accessibility issues invisible.

#### 2.1 Core Component Test Suite

- [ ] **Test `Sidebar.jsx` navigation logic**
  - **Files**: Create `frontend/src/components/__tests__/Sidebar.test.jsx`
  - **Test Cases**:
    - Renders all navigation icons (Brain, Chat, Arena, Knowledge Base)
    - Highlights active route based on `location.pathname`
    - Shows collapse/expand button when `showCollapsible=true`
    - Disables interactions when `disabled=true`
    - Calls `onToggleSidebar` when collapse button clicked
    - Shows download indicator when `isDownloading=true`
  - **Why**: Sidebar used on every page. Route highlighting logic is critical for UX.
  - **Expected**: Sidebar behavior verified for all navigation states.

- [ ] **Test `QuestionInput.jsx` input handling**
  - **Files**: Create `frontend/src/components/__tests__/QuestionInput.test.jsx`
  - **Test Cases**:
    - Renders textarea with placeholder
    - Calls `onSubmit` when Enter pressed (not Shift+Enter)
    - Disables submit button when input empty
    - Shows loading state when `loading=true`
    - Auto-resizes textarea as user types
    - Clears input after submission
  - **Why**: Used in ChatPage, ConversationPage, ArenaPage. Input validation critical.
  - **Expected**: Input edge cases (empty, multiline, submit) work correctly.

- [ ] **Test `MarkdownRenderer.jsx` content rendering**
  - **Files**: Create `frontend/src/components/__tests__/MarkdownRenderer.test.jsx`
  - **Test Cases**:
    - Renders markdown with `react-markdown`
    - Applies syntax highlighting to code blocks
    - Handles empty content gracefully
    - Renders GFM (GitHub Flavored Markdown) features (tables, strikethrough)
  - **Why**: Displays all LLM responses. Incorrect rendering breaks entire chat UX.
  - **Expected**: Markdown parsing works for all common LLM output formats.

- [ ] **Test `ConfirmationModal.jsx` modal logic**
  - **Files**: Create `frontend/src/components/__tests__/ConfirmationModal.test.jsx`
  - **Test Cases**:
    - Shows modal when `isOpen=true`
    - Hides modal when `isOpen=false`
    - Calls `onConfirm` when confirm button clicked
    - Calls `onCancel` when cancel/close button clicked
    - Displays custom title and message props
    - Prevents background interaction when open
  - **Why**: Used for critical actions (delete model, clear data). Broken modals = data loss.
  - **Expected**: Modal show/hide and callback logic verified.

- [ ] **Test `DragDropArea.jsx` file upload**
  - **Files**: Create `frontend/src/components/__tests__/DragDropArea.test.jsx`
  - **Test Cases**:
    - Accepts .pdf and .txt files
    - Rejects unsupported file types (shows warning)
    - Calls `window.electron.getFilePath` for file paths
    - Updates UI when files dragged over
    - Allows multiple file selection
    - Removes files when X button clicked
  - **Why**: Used in TrainingPage and KnowledgeBasePage. File path extraction complex (Electron API + fallback).
  - **Expected**: File filtering and path extraction work on all platforms.

- [ ] **Test `ModelCard.jsx` model display**
  - **Files**: Create `frontend/src/components/__tests__/ModelCard.test.jsx`
  - **Test Cases**:
    - Displays model name, size, quantization
    - Parses metadata string correctly
    - Shows download button for remote models
    - Shows delete button for local models
    - Calls appropriate callbacks on button clicks
    - Handles missing metadata gracefully
  - **Why**: Primary model selection UI. Metadata parsing (`parseMetadata`) error-prone.
  - **Expected**: Model metadata displays correctly for all formats.

- [ ] **Test `HardwareInfo.jsx` hardware display**
  - **Files**: Create `frontend/src/components/__tests__/HardwareInfo.test.jsx`
  - **Test Cases**:
    - Displays backend type (MLX/CUDA/CPU)
    - Shows GPU info when available
    - Shows CPU info for CPU backend
    - Displays memory stats
    - Handles missing hardware data
    - Calls `window.electron.openDirectory` when data folder clicked
  - **Why**: Hardware detection critical for model recommendations. Electron API integration.
  - **Expected**: Hardware data displays for all backend types.

- [ ] **Test `Dropdown.jsx` selection logic**
  - **Files**: Create `frontend/src/components/__tests__/Dropdown.test.jsx`
  - **Test Cases**:
    - Renders options from `options` prop
    - Shows currently selected value
    - Calls `onChange` with selected value
    - Closes dropdown after selection
    - Handles empty options array
  - **Why**: Used for model selection in multiple pages. Controlled component logic must work.
  - **Expected**: Dropdown value updates and triggers parent callbacks.

- [ ] **Test `Spinner.jsx` / `LoadingScreen.jsx` loading states**
  - **Files**: Create `frontend/src/components/__tests__/LoadingStates.test.jsx`
  - **Test Cases**:
    - Spinner renders with animation
    - LoadingScreen shows during app initialization
    - Loading components don't crash with missing props
  - **Why**: Loading states shown frequently. Must be accessible and not interfere with tests.
  - **Expected**: Loading indicators render without errors.

- [ ] **Test `ChatCollapsibleSection.jsx` conversation list**
  - **Files**: Create `frontend/src/components/__tests__/ChatCollapsibleSection.test.jsx`
  - **Test Cases**:
    - Renders conversation list
    - Highlights active conversation
    - Shows delete button on hover
    - Calls `onDelete` when delete clicked
    - Calls `onSelect` when conversation clicked
    - Handles empty conversation list
  - **Why**: Conversation history navigation critical for ChatPage/ConversationPage.
  - **Expected**: Conversation selection and deletion work correctly.

- [ ] **Test modals in `components/modals/`**
  - **Files**: Create `frontend/src/components/modals/__tests__/` directory
  - **Test Cases**:
    - ErrorModal: displays error message, closes on button click
    - WelcomeModal: shows only on first launch, closes correctly
    - DeleteModelModal: confirms deletion, prevents accidental deletion
    - ModelInfoModal: displays model metadata, closes correctly
    - CustomizePromptModal: saves custom prompt, cancels without saving
  - **Why**: 9 modal components with critical user flows. Broken modals = unusable features.
  - **Expected**: All modal open/close/submit flows work correctly.

---

### Category 3: Page Testing (Integration Tests)

**Problem**: 6 pages with complex state management (useState/useEffect/useCallback), API calls, navigation, and side effects—all untested.

**Impact**: Page-level bugs (routing, data fetching, state updates) only caught by users. Refactoring pages is extremely risky.

#### 3.1 Page Integration Tests

- [ ] **Test `App.jsx` backend health check**
  - **Files**: Create `frontend/src/__tests__/App.test.jsx`
  - **Test Cases**:
    - Shows LoadingScreen while checking backend
    - Retries backend health check on failure
    - Renders routes when backend ready
    - Handles backend never becoming ready (shows loading indefinitely)
  - **Why**: App entry point. Backend health check critical for user experience.
  - **Expected**: App waits for backend and doesn't show routes prematurely.

- [ ] **Test `LandingPage.jsx` model management**
  - **Files**: Create `frontend/src/pages/__tests__/LandingPage.test.jsx`
  - **Test Cases**:
    - Fetches local and remote models on mount
    - Filters models by search query
    - Opens download modal for remote models
    - Deletes local models with confirmation
    - Shows hardware info from `/hardware/app_startup`
    - Navigates to training page when model selected
    - Shows welcome modal only on first launch
  - **Why**: Most complex page (726 lines). Model download/delete flows critical.
  - **Expected**: All user flows (search, download, delete) work correctly.

- [ ] **Test `ConversationPage.jsx` chat functionality**
  - **Files**: Create `frontend/src/pages/__tests__/ConversationPage.test.jsx`
  - **Test Cases**:
    - Fetches conversation history on mount
    - Sends message and displays response (streaming)
    - Handles streaming errors gracefully
    - Saves messages to database
    - Generates conversation title automatically
    - Updates settings (temperature, topP, maxTokens)
    - Copies message content to clipboard
    - Stars/unstars messages
    - Switches between conversations
  - **Why**: Core feature (638 lines). Streaming logic, error handling, and state updates complex.
  - **Expected**: Full chat flow (send → stream → save → display) works end-to-end.

- [ ] **Test `ArenaPage.jsx` multi-model comparison**
  - **Files**: Create `frontend/src/pages/__tests__/ArenaPage.test.jsx`
  - **Test Cases**:
    - Adds panels (up to 4 models)
    - Removes panels
    - Sends same query to all models simultaneously
    - Displays streaming responses in each panel
    - Handles partial failures (one model errors, others succeed)
  - **Why**: Unique multi-panel streaming logic. Concurrent requests must work correctly.
  - **Expected**: All panels update independently without race conditions.

- [ ] **Test `TrainingPage.jsx` fine-tuning flow**
  - **Files**: Create `frontend/src/pages/__tests__/TrainingPage.test.jsx`
  - **Test Cases**:
    - Uploads dataset files
    - Validates form (model + name + dataset required)
    - Starts fine-tuning via DownloadModalContext
    - Shows progress during training
    - Handles training errors (displays ErrorModal)
    - Navigates to LandingPage after completion
  - **Why**: Training flow spans multiple contexts and API calls. Validation logic critical.
  - **Expected**: Training submission only succeeds with valid inputs.

- [ ] **Test `KnowledgeBasePage.jsx` RAG assistant creation**
  - **Files**: Create `frontend/src/pages/__tests__/KnowledgeBasePage.test.jsx`
  - **Test Cases**:
    - Uploads knowledge base documents
    - Creates assistant with selected model
    - Opens knowledge base modal via context
    - Validates form (model + name + documents required)
    - Navigates to chat after assistant creation
  - **Why**: RAG feature entry point. Context integration and form validation must work.
  - **Expected**: Assistant creation only succeeds with all required fields.

- [ ] **Test `ChatPage.jsx` conversation initialization**
  - **Files**: Create `frontend/src/pages/__tests__/ChatPage.test.jsx`
  - **Test Cases**:
    - Creates new conversation
    - Selects model from URL parameter
    - Fetches existing conversations
    - Navigates to ConversationPage after creation
    - Handles model not found error
  - **Why**: Entry point for chat. Model selection and conversation creation must work.
  - **Expected**: New conversation created with selected model.

---

### Category 4: Context Testing (State Management)

**Problem**: 2 React contexts managing global state (download progress, knowledge base modals) with complex async operations—all untested.

**Impact**: Context bugs affect multiple pages. Download/training progress broken = unusable app.

#### 4.1 Context Provider Tests

- [ ] **Test `DownloadModalContext.jsx` download/training flow**
  - **Files**: Create `frontend/src/contexts/__tests__/DownloadModalContext.test.jsx`
  - **Test Cases**:
    - Opens confirmation modal when `open()` called
    - Starts download after confirmation
    - Polls `/llms/local/{id}/progress` every 2s
    - Updates progress, status, timeLeft from API
    - Handles download completion (calls onComplete callback)
    - Handles download failure (shows error, calls onError)
    - Supports fine-tuning mode (polls `/train/progress/{id}`)
    - Collapses/expands modal UI
    - Clears interval on unmount
  - **Why**: 295 lines of complex async logic. Used for all downloads and training. Progress polling critical.
  - **Expected**: Download state updates correctly, no memory leaks (interval cleanup).

- [ ] **Test `KnowledgeBaseContext.jsx` modal state**
  - **Files**: Create `frontend/src/contexts/__tests__/KnowledgeBaseContext.test.jsx`
  - **Test Cases**:
    - Opens knowledge base modal when `open()` called
    - Stores knowledge base task data
    - Closes modal when `close()` called
    - Confirms modal when `confirm()` called
  - **Why**: Manages modal state across KnowledgeBasePage and ConversationPage.
  - **Expected**: Modal open/close state synchronized across components.

---

### Category 5: Service/Utility Testing

**Problem**: Service functions (`arenaService.js`) and utilities (`hardwareTransform.js`) handle critical business logic—all untested.

**Impact**: API integration bugs, data transformation errors invisible until runtime.

#### 5.1 Service Tests

- [ ] **Test `arenaService.js` streaming logic**
  - **Files**: Create `frontend/src/services/__tests__/arenaService.test.js`
  - **Test Cases**:
    - Sends POST request to `/arena/{llmId}/query`
    - Streams response chunks via ReadableStream
    - Calls `onStreamChunk` callback for each chunk
    - Returns full text after stream completes
    - Throws error when question empty
    - Throws error when response not ok
  - **Why**: Streaming logic complex (ReadableStream decoder). Used in ArenaPage.
  - **Expected**: Streaming works correctly, errors propagate.

- [ ] **Test `hardwareTransform.js` data transformation**
  - **Files**: Create `frontend/src/utils/__tests__/hardwareTransform.test.js`
  - **Test Cases**:
    - Transforms `/hardware/app_startup` response correctly
    - Handles MLX backend data format
    - Handles CUDA backend data format
    - Handles CPU backend data format
    - Handles missing/malformed hardware data
    - Returns user-friendly error messages
  - **Why**: Hardware data used in LandingPage, TrainingPage, KnowledgeBasePage. Transformation errors break hardware display.
  - **Expected**: All backend types transform correctly.

---

### Category 6: Electron Integration Testing

**Problem**: Electron IPC (`window.electron`, `window.electronAPI`) used in 3+ components with no mocks or integration tests.

**Impact**: Electron-specific features (file picker, data folder) break on updates. No way to test without full Electron app.

#### 6.1 Electron Mock Tests

- [ ] **Create Electron API mocks**
  - **Files**: Create `frontend/__mocks__/electron.js`
  - **Action**:
    ```javascript
    module.exports = {
      contextBridge: {
        exposeInMainWorld: jest.fn()
      },
      ipcRenderer: {
        invoke: jest.fn(),
        on: jest.fn(),
        send: jest.fn()
      }
    };
    ```
  - **Why**: Components using `window.electron` need mocks to render in tests.
  - **Expected**: Components render without Electron runtime.

- [ ] **Test `preload.js` IPC exposure**
  - **Files**: Create `frontend/src/__tests__/preload.test.js`
  - **Test Cases**:
    - Exposes `window.electron.openDirectory`
    - Exposes `window.electron.getFilePath`
    - Exposes `window.electronAPI.openDataFolder`
    - Exposes `window.electronAPI.clearAllData`
    - Uses `webUtils.getPathForFile` when available
    - Falls back to `file.path` when webUtils unavailable
  - **Why**: Preload API contract must match frontend usage. Breakages cause runtime errors.
  - **Expected**: All exposed APIs testable and documented.

- [ ] **Test Electron IPC in components**
  - **Files**: Update component tests (HardwareInfo, DragDropArea)
  - **Test Cases**:
    - HardwareInfo calls `openDirectory` when data folder clicked
    - DragDropArea calls `getFilePath` for uploaded files
    - Components handle Electron API errors gracefully
  - **Why**: IPC calls in components need integration tests (not just unit tests).
  - **Expected**: Electron IPC calls work in component context.

---

### Category 7: API Integration Testing (Mock Backend)

**Problem**: 50+ API calls (`fetch` to `${API_BASE_URL}`) throughout frontend—all untested. No mock backend or fixtures.

**Impact**: Cannot test frontend without running backend. API contract changes break frontend silently.

#### 7.1 API Mock Setup

- [ ] **Create Mock Service Worker (MSW) setup**
  - **Files**: Install MSW: `npm install -D msw@latest`
  - **Action**: Create `frontend/src/mocks/handlers.js`:
    ```javascript
    import { http, HttpResponse } from 'msw';
    import { API_BASE_URL } from '../config/api';
    
    export const handlers = [
      http.get(`${API_BASE_URL}/health/`, () => {
        return HttpResponse.json({ status: 'ok' });
      }),
      
      http.get(`${API_BASE_URL}/llms/local`, () => {
        return HttpResponse.json([
          { id: 1, name: 'llama-2-7b', size: '7B', quantization: 'Q4_K_M' }
        ]);
      }),
      
      http.get(`${API_BASE_URL}/hardware/app_startup`, () => {
        return HttpResponse.json({
          backend_type: 'mlx',
          gpu_info: { name: 'Apple M1 Pro', memory: '16GB' }
        });
      }),
      
      http.post(`${API_BASE_URL}/conversations/`, () => {
        return HttpResponse.json({ id: 1, title: 'New Chat' });
      }),
      
      // Add more handlers for all API endpoints
    ];
    ```
  - **Why**: MSW mocks API at network level (works with fetch). Industry standard for API testing.
  - **Expected**: Tests can control API responses without real backend.

- [ ] **Setup MSW in tests**
  - **Files**: Update `frontend/src/setupTests.js`
  - **Action**:
    ```javascript
    import { setupServer } from 'msw/node';
    import { handlers } from './mocks/handlers';
    
    export const server = setupServer(...handlers);
    
    beforeAll(() => server.listen());
    afterEach(() => server.resetHandlers());
    afterAll(() => server.close());
    ```
  - **Why**: MSW server must run during tests to intercept fetch calls.
  - **Expected**: All fetch calls in tests return mock data.

- [ ] **Create API test fixtures**
  - **Files**: Create `frontend/src/mocks/fixtures/` directory
  - **Action**: Create JSON fixtures for all API responses:
    - `models.json` (local/remote models)
    - `conversations.json` (conversation list)
    - `messages.json` (message history)
    - `hardware.json` (hardware info for each backend type)
    - `training.json` (training progress data)
  - **Why**: Centralized fixtures ensure consistent test data. Easy to update when API changes.
  - **Expected**: Tests use realistic API response data.

- [ ] **Test API error handling**
  - **Files**: Create `frontend/src/__tests__/api-error-handling.test.jsx`
  - **Test Cases**:
    - App handles 500 server errors gracefully
    - App handles 404 not found errors
    - App handles network errors (fetch fails)
    - App retries transient failures
    - Error messages display to user
  - **Why**: Error handling scattered across components. Need centralized error handling tests.
  - **Expected**: All API errors show user-friendly messages, no crashes.

---

### Category 8: End-to-End (E2E) Testing

**Problem**: No E2E tests. User flows (download model → start chat → send message) untested.

**Impact**: Integration between pages, contexts, and backend untested. User-facing bugs only found manually.

#### 8.1 E2E Test Setup (Optional - Lower Priority)

- [ ] **Install Playwright or Cypress**
  - **Files**: `frontend/package.json`
  - **Action**: Choose one:
    - Playwright: `npm install -D @playwright/test` (recommended for Electron)
    - Cypress: `npm install -D cypress`
  - **Why**: E2E tests need real browser + backend. Playwright has better Electron support.
  - **Expected**: E2E framework installed.

- [ ] **Create E2E test for chat flow**
  - **Files**: Create `frontend/e2e/chat-flow.spec.js`
  - **Test Cases**:
    - User navigates to LandingPage
    - User selects model and clicks "Start Chat"
    - User sends message in ChatPage
    - User sees streaming response
    - Message saved to conversation history
  - **Why**: Most critical user flow. Must work end-to-end.
  - **Expected**: Full chat flow works with real backend.

- [ ] **Create E2E test for model download**
  - **Files**: Create `frontend/e2e/model-download.spec.js`
  - **Test Cases**:
    - User clicks download on remote model
    - Download modal opens
    - Progress bar updates
    - Download completes successfully
    - Model appears in local models list
  - **Why**: Download flow spans contexts, pages, and backend. Complex to test.
  - **Expected**: Model download works end-to-end.

- [ ] **Create E2E test for training flow**
  - **Files**: Create `frontend/e2e/training-flow.spec.js`
  - **Test Cases**:
    - User uploads dataset
    - User selects model and enters name
    - User starts training
    - Progress updates during training
    - Training completes, model appears in local models
  - **Why**: Training flow critical for app value proposition. Must work reliably.
  - **Expected**: Full training flow works with real backend.

---

### Category 9: Accessibility (a11y) Testing

**Problem**: No accessibility testing. 22 components, 6 pages with no ARIA attributes, keyboard navigation, or screen reader support.

**Impact**: App unusable for users with disabilities. Legal compliance risk (ADA, WCAG).

#### 9.1 Accessibility Tests

- [ ] **Install jest-axe for automated a11y testing**
  - **Files**: `frontend/package.json`
  - **Action**: `npm install -D jest-axe`
  - **Why**: jest-axe runs axe-core accessibility rules in Jest tests.
  - **Expected**: Can run a11y tests in component tests.

- [ ] **Add a11y tests to all components**
  - **Files**: Update all component test files
  - **Test Cases**:
    - Component has no axe violations
    - Buttons have accessible labels
    - Form inputs have labels/aria-labels
    - Images have alt text
    - Interactive elements keyboard accessible
  - **Why**: Accessibility violations common in untested React apps.
  - **Expected**: All components pass basic a11y tests.

- [ ] **Test keyboard navigation**
  - **Files**: Update page test files
  - **Test Cases**:
    - User can navigate Sidebar with Tab key
    - User can submit QuestionInput with Enter key
    - User can close modals with Escape key
    - User can activate buttons with Space/Enter
  - **Why**: Keyboard navigation critical for accessibility and power users.
  - **Expected**: All interactive elements keyboard accessible.

- [ ] **Test screen reader support**
  - **Files**: Create `frontend/src/__tests__/a11y-screen-reader.test.jsx`
  - **Test Cases**:
    - All buttons have aria-labels
    - Loading states announced to screen readers
    - Error messages announced to screen readers
    - Dynamic content updates announced (aria-live)
  - **Why**: Screen reader users cannot use app without proper ARIA.
  - **Expected**: Screen readers can navigate and use app.

---

### Category 10: Test Coverage and Quality Gates

**Problem**: No coverage tracking, no quality gates. Cannot measure testing progress or enforce standards.

**Impact**: Unknown test coverage. No way to prevent coverage regression.

#### 10.1 Coverage Configuration

- [ ] **Configure coverage collection**
  - **Files**: `frontend/jest.config.js` (already in item 1.1)
  - **Action**: Set coverage thresholds:
    ```javascript
    coverageThresholds: {
      global: {
        branches: 70,
        functions: 70,
        lines: 70,
        statements: 70
      }
    }
    ```
  - **Why**: Coverage thresholds enforce minimum test quality. 70% is professional standard.
  - **Expected**: Tests fail if coverage drops below 70%.

- [ ] **Create coverage report script**
  - **Files**: `frontend/package.json` (already in item 1.1)
  - **Action**: Script already added: `"test:coverage": "jest --coverage"`
  - **Why**: Developers need easy way to check coverage.
  - **Expected**: `npm run test:coverage` generates HTML report.

- [ ] **Add coverage to .gitignore**
  - **Files**: `.gitignore`
  - **Action**: Add:
    ```
    frontend/coverage/
    ```
  - **Why**: Coverage reports are generated files, shouldn't be committed.
  - **Expected**: Coverage reports ignored by Git.

- [ ] **Setup CI to fail on low coverage**
  - **Files**: CI configuration (see CI/CD section in checklist)
  - **Action**: Run `npm run test:ci` in CI pipeline
  - **Why**: Prevents merging PRs with insufficient tests.
  - **Expected**: CI fails if coverage < 70%.

---

### Category 11: Test Organization and Best Practices

**Problem**: No testing standards or patterns defined. Developers don't know how to write tests.

**Impact**: Inconsistent test quality. Difficult to maintain tests.

#### 11.1 Testing Guidelines

- [ ] **Create testing guide**
  - **Files**: Create `frontend/docs/testing-guide.md`
  - **Content**:
    - How to run tests
    - How to write component tests (RTL patterns)
    - How to write page tests (integration patterns)
    - How to mock APIs (MSW examples)
    - How to test async code (waitFor, findBy)
    - How to test Electron APIs
    - AAA pattern (Arrange, Act, Assert)
  - **Why**: Developers need reference for testing patterns.
  - **Expected**: Consistent test quality across team.

- [ ] **Create test utilities**
  - **Files**: Create `frontend/src/test-utils/index.js`
  - **Action**: Custom render function with providers:
    ```javascript
    import { render } from '@testing-library/react';
    import { BrowserRouter } from 'react-router-dom';
    import { DownloadModalProvider } from '../contexts/DownloadModalContext';
    import { KnowledgeBaseProvider } from '../contexts/KnowledgeBaseContext';
    
    export function renderWithProviders(ui, options = {}) {
      return render(
        <BrowserRouter>
          <DownloadModalProvider>
            <KnowledgeBaseProvider>
              {ui}
            </KnowledgeBaseProvider>
          </DownloadModalProvider>
        </BrowserRouter>,
        options
      );
    }
    
    export * from '@testing-library/react';
    export { renderWithProviders as render };
    ```
  - **Why**: All components need router + context providers. DRY principle.
  - **Expected**: Tests use `renderWithProviders` instead of `render`.

- [ ] **Setup pre-commit test hook**
  - **Files**: Install husky: `npm install -D husky lint-staged`
  - **Action**: Create `.husky/pre-commit`:
    ```bash
    #!/bin/sh
    . "$(dirname "$0")/_/husky.sh"
    
    cd frontend && npm test -- --bail --findRelatedTests
    ```
  - **Why**: Catch test failures before commit. Faster than CI.
  - **Expected**: Commits blocked if related tests fail.

---

### Category 12: Console Cleanup and Production Readiness

**Problem**: 40+ `console.log` calls in production code. 30+ `console.error` calls. No structured logging.

**Impact**: Production logs polluted. Debugging difficult. PII/prompts logged to console.

#### 12.1 Console Cleanup

- [ ] **Remove all console.log calls**
  - **Files**: All files in `frontend/src/`
  - **Action**: Replace with proper logging or remove:
    - Debug logs → remove or use debug library
    - User actions → use analytics/telemetry
    - API responses → remove (sensitive data)
  - **Why**: 40+ console.logs found via grep. Console pollution violates engineering guidelines.
  - **Expected**: Zero console.log calls in production code.

- [ ] **Replace console.error with structured error logging**
  - **Files**: All files in `frontend/src/`
  - **Action**: Create `frontend/src/utils/logger.js`:
    ```javascript
    class Logger {
      error(message, error, context = {}) {
        // Send to error tracking service (Sentry, etc.)
        // Don't log PII or prompts
        console.error(`[ERROR] ${message}`, { context });
      }
      
      warn(message, context = {}) {
        console.warn(`[WARN] ${message}`, { context });
      }
    }
    
    export const logger = new Logger();
    ```
  - **Why**: 30+ console.error calls found. Need centralized error logging.
  - **Expected**: All errors logged via logger.error().

- [ ] **Add ESLint rule to block console statements**
  - **Files**: Create `frontend/.eslintrc.js`
  - **Action**:
    ```javascript
    module.exports = {
      rules: {
        'no-console': ['error', { allow: ['warn', 'error'] }]
      }
    };
    ```
  - **Why**: Prevent new console.log calls from being added.
  - **Expected**: ESLint fails if console.log added.

---

### Category 13: Performance Testing

**Problem**: No performance monitoring. Large page components (638-726 lines) with complex state—performance unknown.

**Impact**: App may be slow for users. No baseline for performance regressions.

#### 13.1 Performance Tests

- [ ] **Add React DevTools Profiler to tests**
  - **Files**: Create `frontend/src/__tests__/performance.test.jsx`
  - **Test Cases**:
    - Measure ConversationPage render time
    - Measure LandingPage render time with 50+ models
    - Measure ArenaPage with 4 panels streaming
    - Identify slow components (> 100ms render)
  - **Why**: Large components may have performance issues. Need baseline.
  - **Expected**: Performance benchmarks established.

- [ ] **Test memo optimization**
  - **Files**: Update component tests
  - **Test Cases**:
    - Components re-render only when props change
    - useMemo prevents expensive recalculations
    - useCallback prevents unnecessary child re-renders
  - **Why**: React optimizations (memo, useMemo, useCallback) unused. May cause performance issues.
  - **Expected**: Identify components needing optimization.

---

## Summary: Testing Optimization Impact

**Current State:**
- 0 test files
- 0% code coverage
- 0 testing dependencies
- 40+ console.log statements
- 30+ console.error statements
- No quality gates
- No CI testing
- No accessibility testing

**After Implementation:**
- 50+ test files (components, pages, contexts, services, utils)
- 70%+ code coverage (enforced)
- Professional testing infrastructure (Jest + RTL + MSW)
- Automated a11y testing
- API contract testing
- E2E user flow testing
- Zero console pollution
- CI quality gates
- Pre-commit test hooks

**Expected Outcomes:**
- ✅ Catch regressions before production
- ✅ Refactoring becomes safe
- ✅ Onboarding easier (tests = documentation)
- ✅ Accessibility compliance (WCAG 2.1)
- ✅ Professional code quality standards met
- ✅ User-facing bugs reduced by 70%+
- ✅ CI/CD pipeline enforces quality

**Priority:**
- **P0** (Critical): Category 1-4 (framework setup, component tests, page tests, context tests)
- **P1** (High): Category 5-7 (service tests, Electron tests, API mocks)
- **P2** (Medium): Category 9-12 (a11y, coverage, console cleanup)
- **P3** (Low): Category 8, 13 (E2E, performance)

**Estimated Effort:**
- Setup (Category 1): 4-6 hours
- Component tests (Category 2): 16-20 hours
- Page tests (Category 3): 12-16 hours
- Context/Service tests (Category 4-5): 6-8 hours
- Electron/API mocks (Category 6-7): 8-10 hours
- Total: **46-60 hours** for comprehensive testing infrastructure

