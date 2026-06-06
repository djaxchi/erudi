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
