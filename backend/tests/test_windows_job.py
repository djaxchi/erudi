"""Tests for the Windows job-object orphan fix (#341).

See src/launcher/windows_job.py for the full rationale: a hard-killed
Electron parent can take this process down before either the parent-death
watchdog or the stdin-EOF watcher get a chance to run, so Postgres and
llama-server need their lifetime tied to this process at the kernel level
instead of relying on Python code reacting in time.
"""
from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_noop_off_windows(monkeypatch):
    """Off Windows the function must be a safe, side-effect-free no-op."""
    from src.launcher import windows_job

    monkeypatch.setattr(windows_job.platform, "system", lambda: "Darwin")
    assert windows_job.bind_children_to_this_process() is False


@pytest.mark.unit
@pytest.mark.skipif(platform.system() != "Windows", reason="job-object API is Windows-only")
def test_binds_current_process_on_windows():
    """On a real Windows host, binding must succeed and be safe to call."""
    from src.launcher import windows_job

    assert windows_job.bind_children_to_this_process() is True
    assert windows_job._job_handle is not None


INTERMEDIARY_SOURCE = textwrap.dedent(
    """
    # Stand-in for backend.exe: bind ourselves to a kill-on-close job, spawn a
    # grandchild that just sleeps, report its pid, then idle until killed.
    import json
    import subprocess
    import sys
    import time

    sys.path.insert(0, {backend_dir!r})
    from src.launcher.windows_job import bind_children_to_this_process

    bind_children_to_this_process()

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
    print(json.dumps({{"event": "child_spawned", "child_pid": child.pid}}), flush=True)
    while True:
        time.sleep(3600)
    """
)


@pytest.mark.integration
@pytest.mark.skipif(platform.system() != "Windows", reason="job-object cascade is Windows-only")
def test_grandchild_dies_with_hard_killed_intermediary(tmp_path):
    """The exact #341 reproduction: kill the binder, the grandchild must die too.

    Mirrors test_parent_watchdog_spawn.py's POSIX SIGKILL reproduction, one
    level down: there the assertion is "the backend notices its parent died
    and shuts down cleanly"; here it is "even if the backend gets NO chance to
    react at all, its own children still die" -- the safety net under that
    watchdog, not a replacement for it.
    """
    script = tmp_path / "intermediary.py"
    script.write_text(INTERMEDIARY_SOURCE.format(backend_dir=str(BACKEND_DIR)))

    intermediary = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    child_pid: int | None = None
    try:
        # Skip past any log lines the import path writes to the same stdout
        # (e.g. the logger.info in bind_children_to_this_process itself) --
        # only the printed JSON line matters here.
        deadline = time.time() + 30
        payload = None
        while time.time() < deadline:
            raw = intermediary.stdout.readline()
            if not raw:
                continue
            try:
                candidate = json.loads(raw.decode("utf-8", "replace").strip())
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and "child_pid" in candidate:
                payload = candidate
                break
        assert payload is not None, "intermediary never reported the grandchild pid"
        child_pid = payload["child_pid"]

        # Hard-kill the intermediary the same way Task Manager "End task"
        # would: no cleanup, no signal delivered to its children.
        os.kill(intermediary.pid, signal.SIGTERM)
        intermediary.wait(timeout=10)

        deadline = time.time() + 10
        while time.time() < deadline and _pid_alive(child_pid):
            time.sleep(0.5)
        assert not _pid_alive(child_pid), (
            f"grandchild (pid {child_pid}) survived the intermediary's hard kill: "
            "the job-object binding did not cascade (#341 regression)"
        )
    finally:
        if child_pid is not None and _pid_alive(child_pid):
            _best_effort_kill(child_pid)
        if intermediary.poll() is None:
            _best_effort_kill(intermediary.pid)
        try:
            intermediary.stdout.close()
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    import psutil

    return psutil.pid_exists(pid)


def _best_effort_kill(pid: int | None) -> None:
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
