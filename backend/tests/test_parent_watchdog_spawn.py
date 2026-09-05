"""Integration: a SIGKILLed parent must not leave the backend orphaned (#224).

Reproduces the QA finding on the REAL launcher: Electron's main process gets
SIGKILLed (crash, force-quit, power event), its cleanup never runs, and the
PyInstaller backend plus the embedded Postgres survive, reparented to pid 1
and still holding the port. The invariant under test: the backend detects
parent death ITSELF (ppid watchdog in run.py) and walks the normal clean
shutdown path -- lifespan shutdown, postgres stopped, port released, the
usual ``{"event": "shutdown"}`` emitted -- without depending on a stdout
write to the dead parent.

Harness: an intermediary Python process (stand-in for the Electron main)
spawns the real ``run.py`` with an isolated ``ERUDI_DATA_ROOT`` (throwaway
embedded-Postgres cluster) on an explicit high port (27195-27199, clear of
the canonical 27182 and of the 27200+ inference pools). Once the backend
reports ``ready``, the intermediary is SIGKILLed and the backend must exit
within a bounded window.

POSIX-only: SIGKILL/reparenting semantics. Windows parent death is covered
by the stdin-EOF watcher (ERUDI_WATCH_STDIN, #216) plus the psutil probe
unit-tested in test_launcher.py.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
RUN_PY = BACKEND_DIR / "run.py"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.name != "posix", reason="SIGKILL orphan semantics are POSIX-only"),
]

# Explicit high window: never the canonical 27182 (a live QA/dev backend may
# hold it) and strictly below the inference pools at 27200+.
CANDIDATE_PORTS = range(27195, 27200)

READY_TIMEOUT_SECONDS = 300  # first boot pays a one-time initdb (run.py budget)
EXIT_WINDOW_SECONDS = 15  # watchdog poll + graceful shutdown + postgres stop


def _port_free(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return False
    except OSError:
        return True


def _pick_port() -> int:
    for port in CANDIDATE_PORTS:
        if _port_free(port):
            return port
    pytest.skip("no free port in 27195-27199 (busy test host)")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _best_effort_kill(pid: int | None) -> None:
    """SIGKILL a pid THIS test spawned (never a stranger's process)."""
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _stop_leaked_postgres(instance_root: Path) -> None:
    """Stop the throwaway cluster if a failed run left its postmaster behind.

    Only ever touches the postmaster whose pid is recorded inside OUR
    temp instance dir -- a descendant of this test, never a foreign process.
    """
    pid_file = instance_root / "data" / "postgres" / "postmaster.pid"
    try:
        pid = int(pid_file.read_text().splitlines()[0].strip())
    except (OSError, ValueError, IndexError):
        return
    if not _pid_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 10
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.2)
    if _pid_alive(pid):
        _best_effort_kill(pid)


INTERMEDIARY_SOURCE = textwrap.dedent(
    """
    # Stand-in for the Electron main process: spawn the real launcher as a
    # child (inheriting this process's stdout pipe so the test reads the
    # backend's JSON lifecycle events directly), report the child's pid on
    # the same pipe, then idle until the test SIGKILLs us.
    import json
    import subprocess
    import sys
    import time

    child = subprocess.Popen([sys.executable, sys.argv[1], "--port", sys.argv[2]])
    print(json.dumps({"event": "intermediary_spawned", "backend_pid": child.pid}), flush=True)
    while True:
        time.sleep(3600)
    """
)


def test_backend_exits_after_parent_sigkill(tmp_path):
    port = _pick_port()
    instance_root = tmp_path / "instance"
    script = tmp_path / "intermediary.py"
    script.write_text(INTERMEDIARY_SOURCE)

    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        # Isolated throwaway instance: own embedded-Postgres cluster + logs.
        "ERUDI_DATA_ROOT": str(instance_root),
    }
    # The ppid watchdog must be the ONLY parent-death mechanism at play here.
    env.pop("ERUDI_NO_PARENT_WATCHDOG", None)
    env.pop("ERUDI_WATCH_STDIN", None)

    events: list[dict] = []
    lines: list[str] = []

    def _read(pipe) -> None:
        for raw in pipe:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            lines.append(line)
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)

    def _wait_event(name: str, timeout: float) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for event in list(events):
                if event.get("event") == name:
                    return event
            time.sleep(0.25)
        return None

    intermediary = subprocess.Popen(
        [sys.executable, str(script), str(RUN_PY), str(port)],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    reader = threading.Thread(target=_read, args=(intermediary.stdout,), daemon=True)
    reader.start()

    backend_pid: int | None = None
    try:
        spawned = _wait_event("intermediary_spawned", timeout=30)
        assert spawned is not None, f"intermediary never reported the backend pid: {lines[-15:]}"
        backend_pid = spawned["backend_pid"]

        ready = _wait_event("ready", timeout=READY_TIMEOUT_SECONDS)
        assert ready is not None, f"backend never reported ready: {lines[-25:]}"
        actual_port = ready["port"]

        # The Electron stand-in dies hard: no cleanup, no signal to the child.
        os.kill(intermediary.pid, signal.SIGKILL)
        intermediary.wait(timeout=10)

        # Invariant (#224): the backend notices the reparenting by itself and
        # exits within a bounded window...
        deadline = time.time() + EXIT_WINDOW_SECONDS
        while time.time() < deadline and _pid_alive(backend_pid):
            time.sleep(0.5)
        assert not _pid_alive(backend_pid), (
            f"backend (pid {backend_pid}) survived the parent SIGKILL beyond "
            f"{EXIT_WINDOW_SECONDS}s: orphaned, still holding port {actual_port}"
        )

        # ...releases the port...
        assert _port_free(actual_port), f"port {actual_port} still held after backend exit"

        # ...and went through the NORMAL clean shutdown path: the launcher's
        # usual shutdown event is emitted only after the lifespan shutdown
        # (inference child terminated, embedded Postgres stopped) completed.
        reader.join(timeout=10)
        assert any(
            e.get("event") == "shutdown" for e in events
        ), f"no clean shutdown event observed; tail: {lines[-25:]}"
    finally:
        if backend_pid is not None and _pid_alive(backend_pid):
            _best_effort_kill(backend_pid)
        if intermediary.poll() is None:
            _best_effort_kill(intermediary.pid)
        _stop_leaked_postgres(instance_root)
        try:
            intermediary.stdout.close()
        except OSError:
            pass
