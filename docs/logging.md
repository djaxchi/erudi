# 🪵 Logging & Traceability

Erudi writes two log files. Together they let you follow a single user action
from the click in the UI down to the backend work it triggered.

## Log files

| File | Written by | Contents |
|------|------------|----------|
| `backend.log` | Backend (FastAPI process) | Every HTTP request (method, path, status, duration), model generation lifecycle, knowledge-base ingestion phases, RAG searches |
| `erudi-backend.log` | Electron main process | Backend stdout/stderr (launcher lifecycle events) and every UI interaction from the renderer — clicks, drops, pastes, committed input values — persisted via IPC |

### Where to find them

| File | Development | Packaged app |
|------|-------------|--------------|
| `backend.log` | `backend/logs/backend.log` | macOS: `~/Library/Logs/erudi/backend.log` · Windows: `%LOCALAPPDATA%\erudi\logs\backend.log` · Linux: `${XDG_STATE_HOME:-~/.local/state}/erudi/logs/backend.log` |
| `erudi-backend.log` | OS temp directory (same as packaged) | macOS: `$TMPDIR/erudi-backend.log` (run `echo $TMPDIR` in a terminal to resolve the folder) · Windows: `%TEMP%\erudi-backend.log` · Linux: `/tmp/erudi-backend.log` |

### Rotation

- `backend.log` rotates at 10 MB and keeps up to 10 previous files (`backend.log.1` … `backend.log.10`).
- `erudi-backend.log` rotates at 10 MB and keeps one previous file (`.old`).

All timestamps in both files are UTC, ISO-8601, with milliseconds — so lines
from the two files can be correlated reliably.

## Request-id correlation

Every user interaction in the renderer gets a request id of the form `fe-…`.
The frontend sends it as the `X-Request-ID` header on the resulting API call,
the backend injects the same id into every log line produced while handling
that request, and echoes it back in the response.

One user click therefore leaves this trail:

1. `erudi-backend.log` — the UI event (click, drop, paste, input) with its `fe-…` id.
2. `backend.log` — the HTTP request line and all backend work it triggered (generation, ingestion, RAG search), each line tagged with the same `fe-…` id.

## Log level

The default level is `INFO` everywhere. Set the `ERUDI_LOG_LEVEL` environment
variable to change it — for example `DEBUG` when investigating an issue:

```bash
# Development (backend)
cd backend && ERUDI_LOG_LEVEL=DEBUG python run.py

# Packaged app: set the variable in the environment before launching, e.g. on macOS
ERUDI_LOG_LEVEL=DEBUG open -a Erudi
```

## Tracing a bug (QA recipe)

1. Reproduce the problem and note the time (remember: logs are in UTC).
2. Grab both files from the locations above.
3. In `erudi-backend.log`, find the UI event at that time and copy its `fe-…` request id.
4. Grep `backend.log` for that id — every backend line for that action carries it:

```bash
grep "fe-abc123" backend.log
```

> ⚠️ **Privacy** — logs include conversation and message content as well as
> document names. Review and redact them before sharing publicly, for example
> when attaching them to a GitHub issue.
