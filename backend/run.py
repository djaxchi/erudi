"""Cross-platform launcher for the Erudi FastAPI backend.

This module boots the FastAPI application in a background thread while
emitting newline-delimited JSON events for the Electron frontend. The
launcher is designed to run identically in development (editable source
tree) and in PyInstaller bundles targeting macOS, Windows, and Linux across
CUDA, MLX, and CPU builds.

**Lifecycle events (newline-delimited JSON to stdout):**
    - {"event": "starting", "arch": "...", "mode": "dev|prod", "data_path": "...", "port": N, "first_run": bool}
    - {"event": "phase", "phase": "preparing_database|recovering_database|running_migrations|loading_catalog"}
    - {"event": "ready", "port": N}
    - {"event": "shutdown"}
    - {"event": "startup_error", "code": "ERROR_CODE", "message": "..."}

    Every event also carries {"ts": "<UTC ISO-8601 ms, Z>"} (stamped by
    src.launcher.events.emit_event) so it can be correlated with the backend
    and Electron logs.

**Supported error codes:**
    - NO_PORT_AVAILABLE: Every candidate port in the scan range is busy
    - CRASH_BEFORE_READY: Backend thread exited before binding port
    - PORT_TIMEOUT: Server did not bind within the startup window
    - IMPORT_ERROR: Failed to import FastAPI application
    - DATA_PREP_ERROR: Failed to prepare data directories
    - UNEXPECTED_ERROR: Unhandled exception in server thread
    - POLLING_ERROR: Unhandled exception in startup polling loop

**Key responsibilities:**
    * Parse command-line arguments (--port) for flexible port binding.
    * Normalize environment variables for deterministic third-party libs (TOKENIZERS_PARALLELISM, etc.).
    * Configure asyncio selector policy on Windows for library compatibility.
    * Redirect data/log directories to user-writable locations on bundled builds.
    * Preserve macOS symlink behavior while adopting OS-appropriate folders on Windows/Linux.
    * Initialize multiprocessing spawn settings before importing heavy modules.
    * Guard startup with readiness polling (127.0.0.1:PORT), crash detection, and a
      first-run-aware timeout (longer on first boot, which pays a one-time initdb).
    * Support all build variants (CPU, CUDA, MLX) transparently via ERUDI_BUILD_VARIANT env var.

**Usage:**
    Development:
        PYTHONPATH=backend python backend/run.py --port 8000

    Packaged (PyInstaller):
        ./backend --port 8000

    From Electron (frontend/src/main.js):
        spawn('./backend/backend', ['--port', '8000'])
"""

from __future__ import annotations

import asyncio
import os
import platform
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    import uvicorn
    from src.launcher import RuntimePaths


import argparse

from src.launcher.events import emit_event, emit_phase

STARTUP_TIMEOUT_SECONDS = 120
# First boot also pays a one-time embedded-Postgres initdb (plus a cold disk
# cache / AV first-scan of the freshly extracted bundle), so allow much longer
# before declaring failure. The frontend mirrors this budget.
FIRST_RUN_TIMEOUT_SECONDS = 300
READINESS_POLL_SECONDS = 0.25

# Erudi's canonical port. 27182 = the leading digits of Euler's number e
# (2.7182…) — a wink for an app built for erudites. Practically, it's a good
# choice on every OS: IANA-unassigned, it sits below every OS's ephemeral range
# (Linux 32768–60999, Windows/macOS 49152–65535, plus Windows Hyper-V/WSL
# exclusions live inside that range), and it's clear of the crowded dev/LLM
# defaults Erudi users are likely to run alongside it (Ollama 11434, LM Studio
# 1234, vLLM 8000, llama.cpp/Tomcat 8080). The renderer never assumes this value:
# it learns the *actual* bound port from the `starting`/`ready` events. This is
# only the try-first default; find_available_port() scans forward on collision.
CANONICAL_PORT = 27182
# The backend scans 27182–27199 and stops short of 27200, which is where the
# inference pools live (llama.cpp 27200–27299, MLX 27300–27399) — so the three
# local servers can never fight over a port. Erudi's whole footprint is 271xx–273xx.
PORT_SCAN_COUNT = 18


def parse_args():
    """Parse command-line arguments for launcher."""
    parser = argparse.ArgumentParser(description="Erudi backend launcher")
    parser.add_argument(
        "--port",
        type=int,
        default=CANONICAL_PORT,
        help=f"Port to bind FastAPI server (default: {CANONICAL_PORT})",
    )
    return parser.parse_args()


def configure_library_env() -> None:
    """Set environment defaults to tame noisy third-party libraries."""
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("PYTHONNOUSERSITE", "1")


def set_event_loop_policy() -> None:
    """Force selector event loop on Windows for broader library compatibility."""
    if platform.system() == "Windows":
        from asyncio import WindowsSelectorEventLoopPolicy

        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())


def configure_stdio() -> None:
    """Force UTF-8 (never-raising) line-buffered stdout/stderr.

    The frozen interpreter ignores PYTHONUTF8 (PyInstaller pre-initializes
    CPython), so without this the streams inherit the locale code page
    (cp1252 on Windows) and any Unicode character in a log line blows up the
    console log handler, which writes to sys.stdout (#168). errors="replace"
    is the last-resort net: a log write can degrade a character to '?' but can
    never raise. Line buffering keeps JSON lifecycle events flushed promptly.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(
                    line_buffering=True, encoding="utf-8", errors="replace"
                )
            except Exception:
                pass  # exotic stream: keep whatever it supports


def is_frozen() -> bool:
    """Return True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def backend_root_dir() -> Path:
    """Resolve the backend root directory for both dev and bundled modes."""
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir))

        candidates = [
            exe_dir / "backend",
            bundle_dir / "backend",
            bundle_dir,
        ]
        for candidate in candidates:
            # PyInstaller 6.x onedir: Python src is compiled into PYZ (no src/ dir),
            # but data files like artifacts/ are present in _internal/ (bundle_dir).
            if (candidate / "src").exists() or (candidate / "artifacts").exists():
                return candidate
        # Last resort: prefer bundle_dir (_internal/) over exe_dir so that
        # artifact paths resolve correctly in PyInstaller 6.x onedir builds.
        return bundle_dir if bundle_dir != exe_dir else exe_dir

    return Path(__file__).resolve().parent


def ensure_backend_on_path(backend_dir: Path) -> None:
    """Insert the backend directory on sys.path if needed."""
    backend_str = str(backend_dir)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)


def ensure_working_directory(backend_dir: Path) -> None:
    """Switch the process working directory to the backend root."""
    try:
        os.chdir(backend_dir)
    except Exception:
        pass


def force_mp_spawn() -> None:
    """Configure multiprocessing to use spawn start method safely."""
    try:
        import multiprocessing as mp

        mp.freeze_support()
        try:
            mp.set_start_method("spawn", force=True)
        except RuntimeError:
            pass
        try:
            import torch.multiprocessing as tmp

            tmp.set_start_method("spawn", force=True)
        except Exception:
            pass
    except Exception:
        pass


def compute_first_run(data_dir: Path | str) -> bool:
    """True when the embedded Postgres cluster has not been initialized yet.

    The canonical first-run signal for the whole app is the absence of
    ``<data_dir>/postgres/PG_VERSION`` — pgserver writes it once initdb
    completes. Used to widen the startup budget and to let the frontend show a
    "first launch may take longer" hint.
    """
    return not (Path(data_dir) / "postgres" / "PG_VERSION").exists()


def startup_timeout_seconds(first_run: bool) -> int:
    """Boot budget: longer on first run (one-time initdb), tighter afterwards."""
    return FIRST_RUN_TIMEOUT_SECONDS if first_run else STARTUP_TIMEOUT_SECONDS


def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    """Return True when a TCP connection to the host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def find_available_port(start_port: int, host: str, count: int = PORT_SCAN_COUNT) -> int | None:
    """Find a free port in [start_port, start_port + count). Returns None if all busy."""
    for port in range(start_port, start_port + count):
        if not port_open(host, port):
            return port
    return None


def kill_port_process(port: int) -> bool:
    """Attempt to kill process on given port. Returns True if successful."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=2
        )
        pid = result.stdout.strip()
        if pid:
            subprocess.run(["kill", "-9", pid], timeout=2)
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False


def run_server(server: "uvicorn.Server") -> None:
    """Run the uvicorn server in the current thread; surface unexpected failures.

    uvicorn skips installing its own signal handlers when running outside the
    main thread — main() relays SIGTERM/SIGINT (the Electron quit path) via
    `server.should_exit` so the FastAPI lifespan shutdown actually runs
    (checkpointer close, embedded PostgreSQL stop) before the process exits.
    """
    try:
        server.run()
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        emit_event(
            {
                "event": "startup_error",
                "code": "UNEXPECTED_ERROR",
                "message": f"Server thread crashed: {exc}",
            }
        )
        sys.exit(1)


def main() -> None:
    """Launch the backend, supervising readiness and emitting lifecycle events."""
    args = parse_args()
    requested_port = args.port
    host = "127.0.0.1"

    configure_library_env()
    set_event_loop_policy()
    configure_stdio()

    backend_dir = backend_root_dir()
    ensure_backend_on_path(backend_dir)
    ensure_working_directory(backend_dir)

    mode = "prod" if is_frozen() else "dev"
    try:
        from src.launcher import get_runtime_paths, initialize_runtime_paths

        runtime_paths: "RuntimePaths"
        try:
            runtime_paths = initialize_runtime_paths(
                mode=mode,
                backend_root=backend_dir,
                packaged_data_dir=backend_dir / "data",
            )
        except ValueError:
            runtime_paths = get_runtime_paths()
    except Exception as exc:
        emit_event(
            {
                "event": "startup_error",
                "code": "DATA_PREP_ERROR",
                "message": f"Failed to prepare data directories: {exc}",
            }
        )
        sys.exit(1)
    else:
        data_dir = runtime_paths.data_dir

    force_mp_spawn()

    try:
        from src.main import app as fastapi_app
    except Exception as exc:  # pragma: no cover - defensive
        emit_event(
            {
                "event": "startup_error",
                "code": "IMPORT_ERROR",
                "message": f"Failed to import FastAPI application: {exc}",
            }
        )
        sys.exit(1)

    # Find available port
    port = find_available_port(requested_port, host)
    
    if port is None:
        # Every candidate is busy — last resort, try to reclaim the middle of the
        # scan window. (POSIX-only via lsof/kill; a no-op on Windows, where this
        # branch is effectively unreachable since 18 consecutive busy ports is
        # absurd. NO_PORT_AVAILABLE is a transient code the frontend auto-retries.)
        fallback_port = requested_port + PORT_SCAN_COUNT // 2
        if kill_port_process(fallback_port):
            time.sleep(1)
            if not port_open(host, fallback_port):
                port = fallback_port

        if port is None:
            emit_event(
                {
                    "event": "startup_error",
                    "code": "NO_PORT_AVAILABLE",
                    "message": (
                        f"Ports {requested_port}-{requested_port + PORT_SCAN_COUNT - 1} "
                        f"all busy, failed to free {fallback_port}"
                    ),
                }
            )
            sys.exit(1)

    first_run = compute_first_run(data_dir)
    emit_event(
        {
            "event": "starting",
            "arch": platform.machine(),
            "mode": mode,
            "data_path": str(data_dir),
            "port": port,
            "first_run": first_run,
        }
    )

    import uvicorn

    # Let the FastAPI lifespan emit startup-progress phases on the same stdout
    # stream (same process). Absent (e.g. plain uvicorn in dev), the lifespan
    # simply skips phase emission.
    fastapi_app.state.emit_phase = emit_phase

    server = uvicorn.Server(
        # access_log=False: uvicorn's unstructured per-request lines are
        # replaced by the request-logging middleware (method, path, status,
        # duration, request id — see src.core.api.RequestLoggingMiddleware).
        uvicorn.Config(
            fastapi_app, host=host, port=port, log_level="info", workers=1, access_log=False
        )
    )

    def _request_graceful_shutdown(signum: int, frame: object) -> None:
        # Relay to uvicorn's exit flag: the server thread notices it, drains
        # requests, runs the lifespan shutdown (checkpointer → embedded
        # PostgreSQL), then run_server returns and the join below unblocks.
        server.should_exit = True

    signal.signal(signal.SIGTERM, _request_graceful_shutdown)
    signal.signal(signal.SIGINT, _request_graceful_shutdown)

    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    deadline = time.time() + startup_timeout_seconds(first_run)
    try:
        while time.time() < deadline:
            if port_open(host, port):
                emit_event({"event": "ready", "port": port})
                server_thread.join(timeout=1.0)
                while server_thread.is_alive():
                    time.sleep(1.0)
                    server_thread.join(timeout=1.0)
                emit_event({"event": "shutdown"})
                break

            if not server_thread.is_alive():
                emit_event(
                    {
                        "event": "startup_error",
                        "code": "CRASH_BEFORE_READY",
                        "message": "Backend thread exited before binding the port",
                    }
                )
                sys.exit(1)

            time.sleep(READINESS_POLL_SECONDS)
        else:
            emit_event(
                {
                    "event": "startup_error",
                    "code": "PORT_TIMEOUT",
                    "message": "Server did not bind in time",
                }
            )
            sys.exit(1)
    except KeyboardInterrupt:
        emit_event({"event": "shutdown"})
        sys.exit(0)
    except Exception as exc:  # pragma: no cover - defensive
        emit_event(
            {
                "event": "startup_error",
                "code": "POLLING_ERROR",
                "message": f"Startup polling loop crashed: {exc}",
            }
        )
        sys.exit(1)


if __name__ == "__main__":
    # MUST run before anything else (especially argparse): in PyInstaller
    # bundles the frozen exe is re-invoked as multiprocessing children and the
    # resource tracker. freeze_support() intercepts those relaunches and exits,
    # so our --port argparse never sees their internal args
    # ("-B -S -I -c from multiprocessing...") and the MLX inference subprocess
    # (multiprocessing.Process) can actually spawn.
    import multiprocessing

    multiprocessing.freeze_support()

    # NOTE: no logging.basicConfig here. A root handler would duplicate every
    # "erudi" log line on stdout (the app logger already owns a console
    # handler and propagates to root), polluting the JSON event stream the
    # Electron main process parses. Third-party WARNING+ records without
    # handlers still surface via logging.lastResort (stderr).
    main()
