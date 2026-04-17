"""
Tests for Erudi backend launcher (run.py): argument parsing and JSON event emission.
"""
import sys
import json
import subprocess
import tempfile
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
    # Run launcher with --port 12345, capture stdout
    with tempfile.TemporaryDirectory() as tmpdir:
        launcher = Path(__file__).parent.parent / "run.py"
        result = subprocess.run(
            [sys.executable, str(launcher), "--port", "12345"],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            env={**os.environ, "PYTHONPATH": str(launcher.parent)},
        )
        # Find the 'starting' event in output
        lines = result.stdout.decode().splitlines()
        starting_events = [json.loads(l) for l in lines if 'starting' in l]
        assert starting_events, "No starting event emitted"
        event = starting_events[0]
        assert event["event"] == "starting"
        assert event["port"] == 12345
