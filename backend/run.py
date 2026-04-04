"""Cross-platform launcher for the Erudi FastAPI backend.

This module boots the FastAPI application in a background thread while
emitting newline-delimited JSON events for the Electron frontend. The
launcher is designed to run identically in development (editable source
tree) and in PyInstaller bundles targeting macOS, Windows, and Linux across
CUDA, MLX, and CPU builds.

**Lifecycle events (newline-delimited JSON to stdout):**
    - {"event": "starting", "arch": "...", "mode": "dev|prod", "data_path": "...", "port": N}
    - {"event": "ready", "port": N}
    - {"event": "shutdown"}
    - {"event": "startup_error", "code": "ERROR_CODE", "message": "..."}

**Supported error codes:**
    - PORT_IN_USE: Port already bound by another process
    - CRASH_BEFORE_READY: Backend thread exited before binding port
    - PORT_TIMEOUT: Server did not bind within startup window (120s)
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
    * Guard startup with readiness polling (127.0.0.1:PORT), crash detection, and 120s timeout.
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
import json
import logging
import os
import platform
import socket
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from fastapi import FastAPI
    from src.launcher import RuntimePaths


import argparse

STARTUP_TIMEOUT_SECONDS = 120
READINESS_POLL_SECONDS = 0.25

def parse_args():
    """Parse command-line arguments for launcher."""
    parser = argparse.ArgumentParser(description="Erudi backend launcher")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind FastAPI server (default: 8765)")
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
    """Enable line buffering on stdout/stderr for immediate event emission."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)


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


def emit_event(payload: dict) -> None:
    """Print a structured JSON event for the Electron frontend."""
    print(json.dumps(payload), flush=True)


def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    """Return True when a TCP connection to the host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def find_available_port(start_port: int, host: str) -> int | None:
    """Find available port from start_port to start_port+34. Returns None if all busy."""
    for port in range(start_port, start_port + 35):
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


def run_server(app: "FastAPI", host: str, port: int) -> None:
    """Run uvicorn in the current thread and surface unexpected failures."""
    import uvicorn

    try:
        uvicorn.run(app, host=host, port=port, log_level="info", workers=1, reload=False)
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
        # All ports busy, try killing 8777 (middle of range)
        fallback_port = 8777
        if kill_port_process(fallback_port):
            time.sleep(1)
            if not port_open(host, fallback_port):
                port = fallback_port
        
        if port is None:
            emit_event(
                {
                    "event": "startup_error",
                    "code": "NO_PORT_AVAILABLE",
                    "message": f"Ports {requested_port}-{requested_port+34} all busy, failed to free {fallback_port}",
                }
            )
            sys.exit(1)

    emit_event(
        {
            "event": "starting",
            "arch": platform.machine(),
            "mode": mode,
            "data_path": str(data_dir),
            "port": port,
        }
    )

    server_thread = threading.Thread(target=run_server, args=(fastapi_app, host, port), daemon=True)
    server_thread.start()

    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    main()
