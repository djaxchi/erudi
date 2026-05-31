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
├── base_engine.py            ← abstract base + engine selection logic
├── cuda_engine.py            ← NVIDIA GPU via llama-server subprocess (Windows/Linux)
├── cpu_engine.py             ← CPU via llama-server subprocess (all platforms, fallback)
├── mlx_engine.py             ← Apple Silicon via mlx_lm.server subprocess (macOS ARM)
├── _mlx_server_runner.py     ← picklable target for the MLX server child process
└── embedder_engine.py        ← sentence-transformers for KB and memory
```

All three inference engines follow the same pattern: they spawn an
OpenAI-compatible HTTP server in a child process and talk to it over
`http://127.0.0.1:<port>/v1/chat/completions` (streaming SSE). CPU/CUDA wrap
the `llama-server` binary via `subprocess.Popen`; MLX wraps `mlx_lm.server`
via `multiprocessing.Process` (because PyInstaller frozen builds have no
Python interpreter at `sys.executable` to pass `-m` to). The streaming
loop, port-pick, readiness probe, and termination logic are intentionally
duplicated across the three files — a follow-up PR will factor them into a
shared `_LlamaServerLikeEngine` base.

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
pytest tests/                       # full suite (default)
pytest tests/ -m "not mlx_only"     # skip MLX integration (CI default)
pytest tests/ -m "mlx_only"         # only MLX integration (local Mac)
pytest tests/ -m "e2e"              # only full-stack e2e tests
```

Pytest markers (declared in `backend/pytest.ini`):

- `unit` — fully mocked, no external dep, runs everywhere
- `integration` — cross-component, may hit DB/filesystem
- `mlx_only` — requires Apple Silicon + `mlx-lm` + a downloaded MLX model;
  skipped automatically on Linux CI by `BaseEngine.get_engine() != "MLX_Engine"`
- `e2e` — full-stack via FastAPI TestClient + real model

MLX integration tests use a shared session-scoped fixture
(`mlx_test_model_path`) that downloads `mlx-community/Qwen2.5-0.5B-Instruct-4bit`
(~280 MB, Apache 2.0, no HF license accept) on first run via
`huggingface_hub.snapshot_download` — cached locally afterwards.

Test-mode environment variables:

- `ERUDI_TEST_THINKING=1` — enable the `<think>` token regression suite
  against `mlx-community/Qwen3-0.6B-4bit` (~600 MB)
- `ERUDI_TEST_GEMMA=1` — enable the Gemma `<end_of_turn>` EOS regression
  test against `mlx-community/gemma-3-270m-it-4bit`
- `ERUDI_MLX_TEST_MODEL_DIR=/path` — override the default HF cache for
  the standard MLX test model (offline / pre-seeded environments)
- `ERUDI_MLX_THINKING_MODEL_REPO=mlx-community/...` — override the
  thinking-test model repo
- `ERUDI_FORCE_CPU=1` — short-circuit GPU detection in
  `BaseEngine.get_engine()` to force `CPU_Engine` for testing fallback paths

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
