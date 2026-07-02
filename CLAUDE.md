# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Erudi is

Desktop app that runs open-source LLMs locally. Two processes:

- **Backend** — Python **3.12** FastAPI server (3.12 is required: `pgserver` only ships wheels up to cp312), launched by `backend/run.py`, listens on `127.0.0.1:27182` by default. Routes are mounted under the `/erudi` prefix.
- **Frontend** — Electron + React + Tailwind, packaged with electron-forge. In production the main process spawns the bundled PyInstaller backend executable; in dev it expects the backend to be running already.

Hardware backend is selected at startup by `BaseEngine.get_engine()` (`backend/src/engines/base_engine.py:507`): `MLX_Engine` on macOS ARM, `CUDA_Engine` on Linux/Windows with NVIDIA, `CPU_Engine` otherwise. Set `ERUDI_FORCE_CPU=1` to bypass GPU detection.

**All three engines follow the same pattern**: they spawn an OpenAI-compatible HTTP server in a child process and talk to it over `http://127.0.0.1:<port>/v1/chat/completions` (SSE). The shared lifecycle (port pick, two-stage `/health` + chat-ping probe, SSE byte-buffer parser, atexit storage with proper unregister-on-swap, idle-cleanup active marker, kwarg translation) lives in `BaseChatServerEngine`. `BaseLlamaCppEngine` sits between it and the CPU/CUDA concretes to factor what's specific to the `llama-server` binary (Popen lifecycle, GGUF picker, install-dir resolution, `repetition_penalty → repeat_penalty` kwarg rename). Concrete subclasses implement four small hooks: `_spawn_child` (CPU/CUDA via `subprocess.Popen`, MLX via `multiprocessing.Process(target=run_mlx_vlm_server, ...)` because PyInstaller frozen builds have no Python interpreter at `sys.executable` to pass `-m` to), `_terminate_process`, `_proc_is_alive`, and `_resolve_model_artifact`.

## Common commands

### Backend

```bash
# First-time setup (pick your platform)
bash scripts/dev/backend/setup-mac-silicon.sh
bash scripts/dev/backend/setup-linux-cuda-121.sh
.\scripts\dev\backend\setup-win-cuda-121.ps1

# Build llama.cpp (required before running on macOS/CPU)
bash scripts/dev/backend/build-llamacpp-cpu-macos-silicon.sh

# Run dev server (from repo root). run.py supervises uvicorn and emits
# newline-delimited JSON lifecycle events on stdout — do not replace it
# with a raw `uvicorn` call when testing the Electron integration.
cd backend && source venv/bin/activate && python run.py --port 27182

# Alternative: uvicorn with reload (skips JSON events, fine for API-only work)
cd backend && source venv/bin/activate && PYTHONPATH=. uvicorn src.main:app --reload --port 27182

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

`bash scripts/dev/dev-start.sh` opens two Terminal windows (backend + frontend, macOS only) and kills anything on `BACKEND_PORT` first. Set `BACKEND_PORT` to override 27182.

### Production build

Backend → PyInstaller bundle → copied into `frontend/backend/` → packaged by electron-forge. See `BUILD.md` for the orchestrated scripts; the spec files are `backend/backend.spec` (Windows CUDA), `backend/backend-mac-silicon.spec` (macOS), and `backend/backend-cpu.spec` (Windows CPU).

## Architecture essentials

### Backend layering (DDD)

```
backend/src/
├── main.py              FastAPI app = api.lifespan + register_routers
├── core/                api.py (lifespan, CORS, exception handler), config, logging, exceptions, health
├── engines/             BaseEngine + MLX/CUDA/CPU — single singleton model in memory
├── agents/              LangChain layer: runner (create_agent/turn), prompts, checkpoint (AsyncPostgresSaver)
├── domains/<name>/      endpoints.py → services.py → repository.py → entities/ (Pydantic in schemas.py)
├── entities/            SQLAlchemy ORM models (Conversation, Message, Llm, KnowledgeBase, KnowledgeDocument, …)
├── database/            core.py (init_database/session), seed.py (create_tables, startup_populate_database)
├── ingestion/           KB pipeline: DocumentReader façade + *Extractor backends, cleaning,
│                        3-pass chunking (e5 tokenizer), E5Embeddings, vector_store (rag.kb_chunks)
├── launcher/            runtime_paths.py (packaged vs. dev paths), postgres_runtime.py (embedded cluster)
└── utils/               file_processor (training), kb_utils (hybrid retrieval façade), prompt_utils
```

Routers mounted under `/erudi` (in `core/api.py:register_routers`): `llms`, `hardware`, `arena`, `knowledge_base`, `conversations`, `startup` (from `domains/`) plus `health` (from `core/health.py`, not a domain). There is no `training` router — training lives in `utils/file_processor` and is driven through the `llms` domain. The frontend hits `http://127.0.0.1:27182/erudi/...` (see `frontend/src/config/api.js`).

**Engine singleton.** `BaseEngine` keeps `_model`, `_tokenizer`, `_model_id`, `_last_used` as class attributes shared across requests, guarded by `_lock`. A 300s idle cleanup task (`start_cleanup_task`) is registered in `lifespan`. Don't instantiate engines — call class methods on the result of `BaseEngine.get_engine()`. Selected engine lives in `src.core.config.LLM_Engine`.

**Adding an engine.** Subclass `BaseEngine`, implement every `@abstractmethod` (`quant_and_save_from_hf_format`, `get_model_and_tokenizer`, `generate_stream`, `get_hardware_info`, `warm_up_accelerator`, `get_performance_evaluation`, `get_flat_hardware_data`), then wire it into `BaseEngine.get_engine()`. Keep OS/hardware branching out of services — it belongs in engines.

**Exceptions.** Raise `AppBaseException` subclasses (`EngineException`, `ModelNotFoundException`, `InvalidInputException` in `src/core/exceptions.py`); the global handler in `core/api.py` returns structured JSON. Don't raise bare `Exception` in domain code.

### Launcher contract

`backend/run.py` is **not** a thin wrapper — it's the production entrypoint expected by the Electron main process and emits newline-delimited JSON events on stdout: `starting`, `ready`, `shutdown`, `startup_error` (codes: `PORT_IN_USE`, `CRASH_BEFORE_READY`, `PORT_TIMEOUT`, `IMPORT_ERROR`, `DATA_PREP_ERROR`, `NO_PORT_AVAILABLE`, `UNEXPECTED_ERROR`, `POLLING_ERROR`). It scans ports `27182-27199` (canonical port 27182 — the digits of e; the scan stops short of the inference pools at 27200+) and falls back to killing the PID on the middle of the window if all are busy. Preserve this protocol if you touch the file.

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
├── config/api.js        API_BASE_URL = http://127.0.0.1:27182/erudi
└── utils/               logger, hardwareTransform
```

`nodeIntegration` is off — anything renderer-needs-from-Node goes through `preload.js` via `contextBridge.exposeInMainWorld` and `ipcMain.handle`.

## Conventions

- **Python**: `snake_case` files/functions, `Capitalized_Snake_Case` classes (yes, with underscores — see `MLX_Engine`, `CUDA_Engine`), absolute imports from `src.*`. Use `pathlib.Path`, never string paths. Logging via `from src.core.logging import logger` — no `print()` in production paths.
- **ASCII-only where it executes or gets parsed**: log-message literals (`logger.*(...)` strings) and machine-parsed bundled data files (e.g. `alembic.ini`) must stay ASCII-only — no `→`, `—`, accents (see #168/#149). Non-ASCII is fine in comments and docstrings (Python reads source as UTF-8 regardless of locale).
- **Async-first.** Don't block the event loop with synchronous I/O in endpoints/services.
- **Ruff config** (`backend/ruff.toml`) only enforces `F` + `E7`. `E501`/`E402`/`F841`/`E701` are intentionally ignored — don't reintroduce them as blockers. Black uses `--line-length=100` via pre-commit.
- **Frontend**: ESLint + Prettier are enforced by CI (`lint:check`, `format:check`).
- **Commits**: `type(scope): description` (`feat`, `fix`, `docs`, `chore`, `ci`). Don't mention Claude/AI or add `Co-Authored-By: Claude`.
- **Requirements**: never edit a single platform file blindly. Common deps live in `backend/requirements/meta/base.txt`; platform/hardware specifics in `meta/*-specs.txt`; entrypoints (`entrypoints/dev/*.txt`, `entrypoints/prod/*.txt`) compose them. Read `backend/requirements/README.md` before adding a dep.

## Data and storage

- **Embedded PostgreSQL + pgvector** via `pgserver` (pip wheels, no Docker, no system install). The FastAPI lifespan boots the cluster (`src/launcher/postgres_runtime.py`, data dir `backend/data/postgres/` in dev; user-writable dir via `runtime_paths.py` in packaged builds), creates the `erudi` database + `vector` extension, then binds SQLAlchemy through `init_database(url)` (psycopg3, `postgresql+psycopg://`). Never import `db_engine` by value — read it via `database.core` attributes after init.
- One database, three tenants: business tables in `public` (SQLAlchemy), LangGraph checkpointer tables in `public` (`AsyncPostgresSaver`, conversation state), KB chunks in `rag.kb_chunks` (langchain-postgres `PGVectorStore`).
- Knowledge Base = hybrid retrieval over `rag.kb_chunks`: dense HNSW (cosine) on `multilingual-e5-small` embeddings (384-dim, `query:`/`passage:` prefixes mandatory) + sparse tsvector (`pg_catalog.simple`) fused by RRF (k=60). Ingestion pipeline lives in `src/ingestion/` (DocumentReader → non-destructive cleaning → 3-pass token-accurate chunking ~180 tokens/15 % overlap → `add_kb_chunks`); per-file dedup via `KnowledgeDocument` SHA-256. Images/scanned PDFs are accepted as `pending_vision` (no OCR tier bundled yet). ⚠ langchain-postgres 0.0.17 freezes the first query's `fts_query` on the shared hybrid config — always search through `search_kb_chunks` (fresh config per call).
- Tests run against a REAL throwaway pgserver cluster (session-scoped fixture in `tests/conftest.py`); per-test isolation via outer-transaction rollback. PG sequences are non-transactional — never assert absolute pk values.

## CI gates (must pass before merge)

- **Backend** (`.github/workflows/backend-ci.yml`, Ubuntu + Python 3.12): `compileall`, `ruff check backend/src`, `from src.main import app`, `pytest tests/ -x -q --ignore=tests/e2e`. Engine tests run against `CPU_Engine` only — keep CPU paths working.
- **Frontend** (`.github/workflows/frontend-ci.yml`, Node 20): `npm ci`, `npm run lint:check`, `npm run format:check`.

## Logs

- Backend: `/tmp/erudi-backend.log` (macOS/Linux) or `%TEMP%\erudi-backend.log` (Windows), written by `frontend/src/main.js`. Backend's own logger writes to `backend/logs/app.log`.
- Frontend (production): electron-log default location.

## Conflict with the global CLAUDE.md

Your global rule mandates French responses; the in-repo `.github/copilot-instructions.md` doesn't take a stance, so French stays the default. The repo-level rules on naming, exceptions, async, and engine encapsulation stack on top — no conflicts to flag today.
