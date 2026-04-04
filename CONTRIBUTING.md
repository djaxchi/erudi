# Contributing to Erudi

Thank you for your interest in contributing. This document explains how the project is structured, how to set up a dev environment, and what we expect from pull requests.

---

## Table of Contents

- [How to contribute](#how-to-contribute)
- [Dev environment setup](#dev-environment-setup)
- [Project conventions](#project-conventions)
- [Backend guide](#backend-guide)
- [Frontend guide](#frontend-guide)
- [Submitting a pull request](#submitting-a-pull-request)
- [Good first issues](#good-first-issues)

---

## How to contribute

1. **Open an issue first** for anything non-trivial (new features, engine changes, architecture decisions). It saves everyone time if we align before you write code.
2. **Fork and branch** — branch off `main`, name your branch descriptively (`fix/cpu-engine-converter`, `feat/ollama-backend`, etc.).
3. **Keep PRs focused** — one concern per PR. A bug fix doesn't need a refactor attached.
4. **Test on your platform** — at minimum run the dev stack end-to-end before opening a PR.

---

## Dev environment setup

See [README.md](README.md) for the full setup walkthrough. The short version:

```bash
# 1. Clone
git clone https://github.com/your-org/erudi.git && cd erudi

# 2. Backend (pick your platform script)
bash scripts/dev/backend/setup-mac-silicon.sh

# 3. Build llama.cpp (pick your platform script)
bash scripts/dev/backend/build-llamacpp-cpu-macos-silicon.sh

# 4. Run
cd backend && source venv/bin/activate && python run.py
cd frontend && npm install && npm start
```

---

## Project conventions

### Python

- Python 3.11+
- No type annotations required on code you didn't write, but add them to new public methods
- Logging via the module-level `logger = logging.getLogger(__name__)` — no bare `print()` in production paths
- Exceptions: use `EngineException` (from `src.core.exceptions`) for engine errors, `DatabaseException` for DB errors — don't raise generic `Exception` in domain code
- Keep engine-specific code inside the engine classes (`CUDA_Engine`, `CPU_Engine`, `MLX_Engine`) — `base_engine.py` and `services.py` should stay platform-agnostic

### JavaScript / React

- ESLint config is in `.eslintrc.json` — run `npm run lint` before committing
- Components in `frontend/src/components/`, pages in `frontend/src/pages/`
- IPC between main and renderer goes through `preload.js` — don't add `nodeIntegration: true`

### Git

- Commit messages: short imperative summary (`fix cpu engine frozen mode converter`, not `Fixed the issue with the CPU engine`)
- Don't commit `.env` files, model files, `venv/`, `node_modules/`, or PyInstaller `dist/`/`build/` directories

---

## Backend guide

### Engine system

The backend selects an inference engine at startup based on hardware:

```
src/engines/
├── base_engine.py      ← abstract base + engine selection logic
├── cuda_engine.py      ← NVIDIA GPU via llama-server (Windows/Linux)
├── cpu_engine.py       ← CPU via llama-server (all platforms, fallback)
├── mlx_engine.py       ← Apple Silicon via MLX (macOS ARM)
└── embedder_engine.py  ← sentence-transformers for KB and memory
```

Adding a new engine: subclass `BaseEngine`, implement all abstract methods, register it in `base_engine.get_engine()`.

### API domains

```
src/domains/
├── conversations/      ← chat, message history, context/memory
├── llms/               ← model download, conversion, management
├── knowledge_base/     ← PDF ingestion, FAISS indexing, RAG
├── hardware/           ← hardware detection and scoring
└── startup/            ← first-run seeding, job cleanup
```

Each domain has `endpoints.py` (FastAPI routes), `services.py` (business logic), `repository.py` (DB queries), and `schemas.py` (Pydantic models).

### Running backend tests

```bash
cd backend
source venv/bin/activate
pytest tests/
```

---

## Frontend guide

The frontend is Electron + React, bundled with webpack via electron-forge.

```
frontend/src/
├── main.js             ← Electron main process (backend lifecycle, IPC)
├── preload.js          ← IPC bridge (contextBridge)
├── renderer.js         ← React entry point
├── pages/              ← top-level route components
├── components/         ← shared UI components
└── services/api/       ← API client wrappers
```

### Useful commands

```bash
cd frontend

npm start           # dev mode (hot reload)
npm run lint        # ESLint
npm run package     # package without installer (for testing)
npm run dist:win    # full Windows installer build
```

### IPC pattern

Main process exposes handlers in `main.js` via `ipcMain.handle(...)`. The renderer calls them via the preload bridge:

```javascript
// preload.js — exposed to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
  // ...
})

// In renderer
const path = await window.electronAPI.openDirectory()
```

Don't call Node APIs directly from renderer code.

---

## Submitting a pull request

1. Make sure `npm run lint` passes (frontend)
2. Make sure `pytest tests/` passes (backend)
3. Test the full dev stack end-to-end on your platform
4. Write a clear PR description: what changed, why, and how to test it
5. Reference any related issues (`Closes #123`)

PRs that touch engine code (`cuda_engine.py`, `cpu_engine.py`, `mlx_engine.py`, `base_engine.py`) should be tested on the relevant platform before merging.

---

## Good first issues

Look for issues tagged `good first issue` on GitHub. Some areas that are always welcome:

- **Documentation** — improve setup guides, add docstrings to undocumented methods
- **Tests** — the test suite has gaps, especially around engine selection and model download flows
- **Linux support** — the CUDA and CPU engines work on Linux but the build pipeline hasn't been tested there
- **Error messages** — many engine errors surface as generic 500s; better user-facing messages are always useful
