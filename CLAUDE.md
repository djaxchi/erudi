# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Erudi is

Desktop app that runs open-source LLMs locally. Two processes:

- **Backend** — Python 3.11+ FastAPI server, launched by `backend/run.py`, listens on `127.0.0.1:8765` by default. Routes are mounted under the `/erudi` prefix.
- **Frontend** — Electron + React + Tailwind, packaged with electron-forge. In production the main process spawns the bundled PyInstaller backend executable; in dev it expects the backend to be running already.

Hardware backend is selected at startup by `BaseEngine.get_engine()` (`backend/src/engines/base_engine.py:507`): `MLX_Engine` on macOS ARM, `CUDA_Engine` on Linux/Windows with NVIDIA, `CPU_Engine` otherwise. Set `ERUDI_FORCE_CPU=1` to bypass GPU detection.

**All three engines follow the same pattern** (`refactor/mlx-server-subprocess`): they spawn an OpenAI-compatible HTTP server in a child process and talk to it over `http://127.0.0.1:<port>/v1/chat/completions` (SSE). CPU/CUDA wrap the `llama-server` binary via `subprocess.Popen`; MLX wraps `mlx_lm.server` via `multiprocessing.Process(target=run_mlx_server, ...)` because PyInstaller frozen builds have no Python interpreter at `sys.executable` to pass `-m` to. The streaming loop, port-pick, readiness probe (`/health` for MLX, ping for CPU/CUDA), and termination logic are intentionally duplicated across the three engine files — a follow-up PR will factor them into a shared `_LlamaServerLikeEngine` base.

## Common commands

### Backend

```bash
# First-time setup (pick your platform)
bash scripts/dev/backend/setup-mac-silicon.sh
bash scripts/dev/backend/setup-mac-intel.sh
bash scripts/dev/backend/setup-linux-cuda-121.sh
.\scripts\dev\backend\setup-win-cuda-121.ps1

# Build llama.cpp (required before running on macOS/CPU)
bash scripts/dev/backend/build-llamacpp-cpu-macos-silicon.sh

# Run dev server (from repo root). run.py supervises uvicorn and emits
# newline-delimited JSON lifecycle events on stdout — do not replace it
# with a raw `uvicorn` call when testing the Electron integration.
cd backend && source venv/bin/activate && python run.py --port 8765

# Alternative: uvicorn with reload (skips JSON events, fine for API-only work)
cd backend && source venv/bin/activate && PYTHONPATH=. uvicorn src.main:app --reload --port 8765

# Tests
cd backend && pytest tests/                              # full suite (local Mac)
cd backend && pytest tests/test_engines.py -x            # single file
cd backend && pytest tests/ -k "test_name"               # by name
cd backend && pytest tests/ --ignore=tests/e2e -m "not mlx_only"  # CI mode (Linux)
cd backend && pytest tests/ -m mlx_only                  # MLX integration only (Mac)
ERUDI_TEST_THINKING=1 pytest tests/ -k thinking          # opt-in regression: <think> tokens
ERUDI_TEST_GEMMA=1 pytest tests/ -k gemma                # opt-in regression: Gemma <end_of_turn> EOS

# Lint
cd backend && ruff check src
```

`pytest.ini` sets `asyncio_mode = auto`, `pythonpath = .`, and `addopts = --strict-markers` — any `@pytest.mark.<name>` not declared in `pytest.ini:markers` is a hard error. Declared markers: `unit`, `integration`, `mlx_only`, `e2e`. Imports use `from src.*` and `from tests._helpers import is_mlx_platform` (etc.) for the platform-skip helpers.

MLX integration tests rely on a session-scoped fixture (`mlx_test_model_path` in `tests/conftest.py`) that downloads `mlx-community/Qwen2.5-0.5B-Instruct-4bit` (~280 MB, Apache 2.0, no HF license accept) on first run. The fixture `pytest.skip`s cleanly on non-MLX hosts.

### Frontend

```bash
cd frontend
npm install              # first time
npm start                # dev mode (expects backend already running)
npm run lint             # ESLint with autofix
npm run lint:check       # ESLint without autofix (matches CI)
npm run format:check     # Prettier check (matches CI)
npm run package          # build app without installer
npm run make             # build + installer (DMG/ZIP/DEB/RPM)
npm run dist:mac         # macOS arm64 via electron-builder
npm run dist:win         # Windows x64 via electron-builder
```

### Combined dev workflow

`bash scripts/dev/dev-start.sh` opens two Terminal windows (backend + frontend, macOS only) and kills anything on `BACKEND_PORT` first. Set `BACKEND_PORT` to override 8765.

### Production build

Backend → PyInstaller bundle → copied into `frontend/backend/` → packaged by electron-forge. See `BUILD.md` for the orchestrated scripts; the spec files are `backend/backend.spec` (Windows CUDA), `backend/backend-mac-silicon.spec` (macOS), and `backend/backend-cpu.spec` (Windows CPU).

## Architecture essentials

### Backend layering (DDD)

```
backend/src/
├── main.py              FastAPI app = api.lifespan + register_routers
├── core/                api.py (lifespan, CORS, exception handler), config, logging, exceptions, health
├── engines/             BaseEngine + MLX/CUDA/CPU/Embedder — single singleton model in memory
├── domains/<name>/      endpoints.py → services.py → repository.py → entities/ (Pydantic in schemas.py)
├── entities/            SQLAlchemy ORM models (Conversation, Message, Llm, KnowledgeBase, VectorStore, …)
├── database/            core.py (engine/session), seed.py (create_tables, startup_populate_database)
├── launcher/            runtime_paths.py — packaged vs. dev path resolution
└── utils/               file_processor, kb_utils (FAISS retrieval), prompt_utils (multi-tier memory)
```

Domains exposed under `/erudi`: `llms`, `training`, `hardware`, `arena`, `knowledge_base`, `conversations`, `health`, `startup`. The frontend hits `http://127.0.0.1:8765/erudi/...` (see `frontend/src/config/api.js`).

**Engine singleton.** `BaseEngine` keeps `_model`, `_tokenizer`, `_model_id`, `_last_used` as class attributes shared across requests, guarded by `_lock`. A 300s idle cleanup task (`start_cleanup_task`) is registered in `lifespan`. Don't instantiate engines — call class methods on the result of `BaseEngine.get_engine()`. Selected engine lives in `src.core.config.LLM_Engine`.

**Adding an engine.** Subclass `BaseEngine`, implement every `@abstractmethod` (`quant_and_save_from_hf_format`, `get_model_and_tokenizer`, `generate_stream`, `get_hardware_info`, `warm_up_accelerator`, `get_performance_evaluation`, `get_flat_hardware_data`), then wire it into `BaseEngine.get_engine()`. Keep OS/hardware branching out of services — it belongs in engines.

**Exceptions.** Raise `AppBaseException` subclasses (`EngineException`, `ModelNotFoundException`, `InvalidInputException` in `src/core/exceptions.py`); the global handler in `core/api.py` returns structured JSON. Don't raise bare `Exception` in domain code.

### Launcher contract

`backend/run.py` is **not** a thin wrapper — it's the production entrypoint expected by the Electron main process and emits newline-delimited JSON events on stdout: `starting`, `ready`, `shutdown`, `startup_error` (codes: `PORT_IN_USE`, `CRASH_BEFORE_READY`, `PORT_TIMEOUT`, `IMPORT_ERROR`, `DATA_PREP_ERROR`, `NO_PORT_AVAILABLE`, `UNEXPECTED_ERROR`, `POLLING_ERROR`). It scans ports `8765-8799` and falls back to killing PID on 8777 if all are busy. Preserve this protocol if you touch the file.

### Frontend layering

```
frontend/src/
├── main.js              Electron main: spawns/kills backend (process group on POSIX,
│                        taskkill /F /T on Windows), parses backend JSON events,
│                        owns auto-update via electron-updater
├── preload.js           contextBridge surface for the renderer
├── renderer.js          React entry
├── App.jsx              react-router-dom routes
├── pages/               top-level screens (ChatPage, ConversationPage, ArenaPage, …)
├── components/          shared UI (Tailwind + lucide-react + framer-motion)
├── contexts/            React contexts (KnowledgeBase, DownloadModal)
├── services/api/client.js  fetch wrapper with retry + timeout + error normalization
├── config/api.js        API_BASE_URL = http://127.0.0.1:8765/erudi
└── utils/               logger, hardwareTransform
```

`nodeIntegration` is off — anything renderer-needs-from-Node goes through `preload.js` via `contextBridge.exposeInMainWorld` and `ipcMain.handle`.

## Conventions

- **Python**: `snake_case` files/functions, `Capitalized_Snake_Case` classes (yes, with underscores — see `MLX_Engine`, `CUDA_Engine`), absolute imports from `src.*`. Use `pathlib.Path`, never string paths. Logging via `from src.core.logging import logger` — no `print()` in production paths.
- **Async-first.** Don't block the event loop with synchronous I/O in endpoints/services.
- **Ruff config** (`backend/ruff.toml`) only enforces `F` + `E7`. `E501`/`E402`/`F841`/`E701` are intentionally ignored — don't reintroduce them as blockers. Black uses `--line-length=100` via pre-commit.
- **Frontend**: ESLint + Prettier are enforced by CI (`lint:check`, `format:check`).
- **Commits**: `type(scope): description` (`feat`, `fix`, `docs`, `chore`, `ci`). Don't mention Claude/AI or add `Co-Authored-By: Claude`.
- **Requirements**: never edit a single platform file blindly. Common deps live in `backend/requirements/meta/base.txt`; platform/hardware specifics in `meta/*-specs.txt`; entrypoints (`entrypoints/dev/*.txt`, `entrypoints/prod/*.txt`) compose them. Read `backend/requirements/README.md` before adding a dep.

## Data and storage

- SQLite via SQLAlchemy. In dev the DB lives under `backend/data/`; in packaged builds `src/launcher/runtime_paths.py` redirects to a user-writable directory (Application Support / AppData / XDG_DATA_HOME) and `run.py`'s `ensure_working_directory` chdirs into the backend root.
- Knowledge Base = FAISS `IndexFlatL2` on `paraphrase-multilingual-MiniLM-L12-v2` embeddings (384-dim, ~384-token chunks, 15% overlap). Retrieval lives in `src/utils/kb_utils.py`; storage mapping is `entities/VectorStore.py`.
- Conversation memory is multi-tier (short-term turns + middle-term vector search + long-term summary + KB top-k) and sized by model in `src/utils/prompt_utils.py`.

## CI gates (must pass before merge)

- **Backend** (`.github/workflows/backend-ci.yml`, Ubuntu + Python 3.12): `compileall`, `ruff check backend/src`, `from src.main import app`, `pytest tests/ -x -q --ignore=tests/e2e`. Engine tests run against `CPU_Engine` only — keep CPU paths working.
- **Frontend** (`.github/workflows/frontend-ci.yml`, Node 20): `npm ci`, `npm run lint:check`, `npm run format:check`.

## Logs

- Backend: `/tmp/erudi-backend.log` (macOS/Linux) or `%TEMP%\erudi-backend.log` (Windows), written by `frontend/src/main.js`. Backend's own logger writes to `backend/logs/app.log`.
- Frontend (production): electron-log default location.

## Conflict with the global CLAUDE.md

Your global rule mandates French responses; the in-repo `.github/copilot-instructions.md` doesn't take a stance, so French stays the default. The repo-level rules on naming, exceptions, async, and engine encapsulation stack on top — no conflicts to flag today.
