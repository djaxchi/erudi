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
def test_default_port_is_canonical_27182(monkeypatch):
    # Erudi's canonical port: the leading digits of e (2.7182…).
    import run
    monkeypatch.setattr(sys, "argv", ["run.py"])
    assert run.parse_args().port == 27182
    assert run.CANONICAL_PORT == 27182


@pytest.mark.unit
def test_backend_scan_stays_below_inference_pools(monkeypatch):
    # The backend scans 27182–27199 and must stop short of 27200, where the
    # inference pools begin (llama.cpp 27200–27299, MLX 27300–27399), so the
    # three local servers never contend for a port.
    import run

    assert run.CANONICAL_PORT + run.PORT_SCAN_COUNT <= 27200

    # With every candidate free, it returns the canonical port; the highest port
    # it can ever return stays inside the backend's own window.
    monkeypatch.setattr(run, "port_open", lambda host, port, timeout=0.4: False)
    assert run.find_available_port(run.CANONICAL_PORT, "127.0.0.1") == run.CANONICAL_PORT

    # With everything busy, it gives up (None) rather than wandering into 27200+.
    monkeypatch.setattr(run, "port_open", lambda host, port, timeout=0.4: True)
    assert run.find_available_port(run.CANONICAL_PORT, "127.0.0.1") is None


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


@pytest.mark.unit
def test_configure_stdio_forces_utf8_replace(monkeypatch):
    # The frozen interpreter ignores PYTHONUTF8, so configure_stdio must pin
    # both streams to UTF-8 with errors="replace" (never-raising) and keep them
    # line-buffered — otherwise a Unicode log line kills the handler (#168).
    import run

    class FakeStream:
        def __init__(self):
            self.kwargs = None

        def reconfigure(self, **kwargs):
            self.kwargs = kwargs

    fake_out = FakeStream()
    fake_err = FakeStream()
    monkeypatch.setattr(sys, "stdout", fake_out)
    monkeypatch.setattr(sys, "stderr", fake_err)

    run.configure_stdio()

    for stream in (fake_out, fake_err):
        assert stream.kwargs == {
            "line_buffering": True,
            "encoding": "utf-8",
            "errors": "replace",
        }


@pytest.mark.unit
def test_configure_library_env_sets_defaults(monkeypatch):
    # configure_library_env pins noisy-library defaults, including
    # HF_HUB_DISABLE_TELEMETRY=1 for local-first egress hygiene (#109).
    import run

    for key in (
        "TOKENIZERS_PARALLELISM",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "PYTHONNOUSERSITE",
        "HF_HUB_DISABLE_TELEMETRY",
    ):
        monkeypatch.delenv(key, raising=False)

    run.configure_library_env()

    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert os.environ["TOKENIZERS_PARALLELISM"] == "false"
    assert os.environ["OMP_NUM_THREADS"] == "1"
    assert os.environ["MKL_NUM_THREADS"] == "1"
    assert os.environ["PYTHONNOUSERSITE"] == "1"


@pytest.mark.unit
def test_configure_library_env_does_not_override_existing(monkeypatch):
    # setdefault semantics: an operator-provided telemetry setting is respected.
    import run

    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "0")
    run.configure_library_env()
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "0"


@pytest.mark.unit
def test_configure_stdio_survives_streams_without_reconfigure(monkeypatch):
    # Some streams (bare objects, or ones that reject reconfigure kwargs) must
    # not break startup — configure_stdio guards each stream individually.
    import run

    class NoReconfigure:
        pass

    class RaisingStream:
        def reconfigure(self, **kwargs):
            raise TypeError("reconfigure not supported")

    # Bare stream with no reconfigure attribute at all.
    monkeypatch.setattr(sys, "stdout", NoReconfigure())
    monkeypatch.setattr(sys, "stderr", NoReconfigure())
    run.configure_stdio()  # must not raise

    # Stream whose reconfigure raises: swallowed by the per-stream guard.
    monkeypatch.setattr(sys, "stdout", RaisingStream())
    monkeypatch.setattr(sys, "stderr", RaisingStream())
    run.configure_stdio()  # must not raise


@pytest.mark.unit
def test_stdin_watch_enabled_reads_env(monkeypatch):
    # Opt-in: only ERUDI_WATCH_STDIN=1 turns the stdin-EOF watcher on. Anything
    # else (unset, "0", "true") leaves it off so dev runs and the subprocess
    # launcher test never grow a stdin reader.
    import run

    monkeypatch.delenv("ERUDI_WATCH_STDIN", raising=False)
    assert run.stdin_watch_enabled() is False

    monkeypatch.setenv("ERUDI_WATCH_STDIN", "0")
    assert run.stdin_watch_enabled() is False

    monkeypatch.setenv("ERUDI_WATCH_STDIN", "1")
    assert run.stdin_watch_enabled() is True


class _FakeStdin:
    """Stand-in for sys.stdin exposing a real fileno() for os.read (#283).

    The watcher now reads the RAW fd (os.read on fileno()), never a buffered
    object, so the fakes hand it a real OS file descriptor: the read end of an
    os.pipe(). Closing the write end delivers EOF (os.read -> b"").
    """

    def __init__(self, fd):
        self._fd = fd

    def fileno(self):
        return self._fd


@pytest.mark.unit
def test_stdin_eof_watcher_sets_should_exit(monkeypatch):
    # An EOF on stdin (parent closed the pipe) must flip uvicorn's exit flag so
    # the FastAPI lifespan shutdown runs — the Windows equivalent of the SIGTERM
    # relay, since Windows has no SIGTERM to catch.
    import run

    read_fd, write_fd = os.pipe()

    class FakeServer:
        should_exit = False

    monkeypatch.setattr(sys, "stdin", _FakeStdin(read_fd))
    server = FakeServer()

    try:
        thread = run.start_stdin_eof_watcher(server)
        # Closing the write end delivers EOF to os.read(read_fd, ...).
        os.close(write_fd)
        thread.join(timeout=2.0)
    finally:
        os.close(read_fd)

    assert not thread.is_alive()
    assert server.should_exit is True


@pytest.mark.unit
def test_stdin_eof_watcher_survives_broken_stdin(monkeypatch):
    # A stdin whose raw read raises must not crash the launcher (the thread just
    # exits) and must leave the exit flag untouched. A closed fd makes os.read
    # raise OSError(EBADF).
    import run

    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    os.close(write_fd)  # fd is now invalid -> os.read raises

    class FakeServer:
        should_exit = False

    monkeypatch.setattr(sys, "stdin", _FakeStdin(read_fd))
    server = FakeServer()

    thread = run.start_stdin_eof_watcher(server)
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert server.should_exit is False


@pytest.mark.unit
def test_stdin_eof_watcher_survives_none_stdin(monkeypatch):
    # No controlling stdin (sys.stdin is None, as under some frozen/detached
    # launches) must return immediately without touching the exit flag (#283).
    import run

    class FakeServer:
        should_exit = False

    monkeypatch.setattr(sys, "stdin", None)
    server = FakeServer()

    thread = run.start_stdin_eof_watcher(server)
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert server.should_exit is False


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
