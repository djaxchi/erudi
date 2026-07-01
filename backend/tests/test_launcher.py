"""
Tests for Erudi backend launcher (run.py): argument parsing and JSON event emission.
"""
import sys
import json
import subprocess
import os
import pytest
from pathlib import Path

LAUNCHER_PATH = Path(__file__).parent.parent / "run.py"

@pytest.mark.parametrize("port", [8000, 9000, 12345])
def test_argparse_port(monkeypatch, port):
    import run
    monkeypatch.setattr(sys, "argv", ["run.py", "--port", str(port)])
    args = run.parse_args()
    assert args.port == port


@pytest.mark.unit
def test_compute_first_run(tmp_path):
    import run

    # No postgres/PG_VERSION yet -> first run.
    assert run.compute_first_run(tmp_path) is True

    pgdata = tmp_path / "postgres"
    pgdata.mkdir()
    (pgdata / "PG_VERSION").write_text("16\n")
    assert run.compute_first_run(tmp_path) is False


@pytest.mark.unit
def test_startup_timeout_is_first_run_aware():
    import run

    assert run.startup_timeout_seconds(True) == run.FIRST_RUN_TIMEOUT_SECONDS
    assert run.startup_timeout_seconds(False) == run.STARTUP_TIMEOUT_SECONDS
    assert run.FIRST_RUN_TIMEOUT_SECONDS > run.STARTUP_TIMEOUT_SECONDS


def test_json_event_emission():
    import time

    launcher = Path(__file__).parent.parent / "run.py"
    proc = subprocess.Popen(
        [sys.executable, str(launcher), "--port", "12345"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": str(launcher.parent)},
    )

    starting_events = []
    deadline = time.time() + 15

    try:
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            decoded = line.decode().strip()
            if not decoded:
                continue
            try:
                event = json.loads(decoded)
                if event.get("event") == "starting":
                    starting_events.append(event)
                    break
            except json.JSONDecodeError:
                pass
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    assert starting_events, "No starting event emitted"
    event = starting_events[0]
    assert event["event"] == "starting"
    assert event["port"] == 12345
    assert "first_run" in event
    assert isinstance(event["first_run"], bool)
