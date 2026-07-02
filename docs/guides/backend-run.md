---
title: Backend Launcher
description: How the unified Erudi backend launcher works in development and production.
---

# Backend Launcher Guide

The `backend/run.py` module provides a single entrypoint for launching the Erudi FastAPI backend across every build target: macOS (Intel/Apple Silicon), Windows (CUDA/CPU), and Linux (CUDA/CPU). It is also used locally during development. The launcher prints newline-delimited JSON events so the Electron shell can track backend state (`starting`, `ready`, `shutdown`, and `startup_error` with specific `code` values).

## Responsibilities

- Configure third-party libraries for deterministic, low-noise startup (Torch, tokenizers, MKL).
- Force the Windows selector event loop policy to maximize library compatibility.
- Normalize stdout/stderr to line-buffered mode so lifecycle events flush immediately.
- Detect PyInstaller bundles and relocate runtime data/logs to OS-appropriate, user-writable folders.
- Preserve the macOS `~/Library/Application Support/erudi/backend/prod` symlink behaviour.
- Initialize multiprocessing with the `spawn` strategy before importing heavy modules (Torch, FastAPI).
- Launch uvicorn on `127.0.0.1:27182` (scanning 27182-27199 if busy) inside a background thread, monitor readiness, and emit structured error events for crashes, timeouts, or port conflicts.

## Data and Log Locations

| Mode | Data Directory | Log Directory |
|------|----------------|---------------|
| Development | `backend/data` | `backend/logs` |
| macOS bundle | `~/Library/Application Support/erudi/backend/prod/data` | `~/Library/Logs/erudi` |
| Windows bundle | `%LOCALAPPDATA%\erudi\backend\prod\data` | `%LOCALAPPDATA%\erudi\logs` |
| Linux bundle | `${XDG_DATA_HOME:-~/.local/share}/erudi/backend/prod/data` | `${XDG_STATE_HOME:-~/.local/state}/erudi/logs` |

`backend/run.py` initializes `src.launcher.runtime_paths` with these directories so the rest of the backend (notably `src/core/config.py` and `src/core/logging.py`) adopts the same locations immediately on import.

The backend writes its log to `backend.log` inside the log directory (rotating file, 10 MB, 10 backups). See [Logging & Traceability](../logging.md) for the full picture, including the Electron-side log and request-id correlation.

## Lifecycle Events

- `{"event":"starting","arch":...,"mode":...,"data_path":...}`
- `{"event":"ready","port":27182}`
- `{"event":"shutdown"}`
- `{"event":"startup_error","code":...,"message":...}`

Error codes include: `DATA_PREP_ERROR`, `IMPORT_ERROR`, `PORT_IN_USE`, `CRASH_BEFORE_READY`, `PORT_TIMEOUT`, `UNEXPECTED_ERROR`, and `POLLING_ERROR`.

## Usage

- **Development**: `cd backend && python run.py`
- **Bundled build**: PyInstaller executes the same module; no platform-specific launchers are required.
- The frontend should read stdout line-by-line and act on the JSON events. A non-zero process exit code signals a startup failure.
