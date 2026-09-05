"""`BaseLlamaCppEngine` must wire the output drainer in, and read from it.

Companion to `test_child_output_drainer.py` (#361): that file proves the
drainer works, this one proves the engine actually uses it -- both at spawn
time (so the pipe is drained for the child's whole life) and on the crash
path (so the error message carries the child's own last words instead of
pointing at logs nothing ever wrote).
"""

import subprocess
import sys

import pytest

from src.core.exceptions import EngineException
from src.engines.child_output import ChildOutputDrainer
from src.engines.cpu_engine import CPU_Engine


def _fake_child(script: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )


class TestSpawnAttachesADrainer:
    def test_spawn_child_attaches_a_drainer_to_the_popen(self, tmp_path, monkeypatch):
        """The pipe must be drained from the moment the child exists."""
        model = tmp_path / "model.gguf"
        model.write_bytes(b"")
        monkeypatch.setattr(
            CPU_Engine,
            "_find_llama_server",
            classmethod(lambda cls, d=None: tmp_path / "llama-server"),
        )
        monkeypatch.setattr(
            CPU_Engine,
            "_build_spawn_argv",
            classmethod(lambda cls, **kw: [sys.executable, "-c", "import time;time.sleep(30)"]),
        )

        handle = CPU_Engine._spawn_child(model_path=model, alias="a", port=27200)
        proc = handle["proc"]
        try:
            drainer = CPU_Engine._output_drainer_for(proc)
            assert isinstance(drainer, ChildOutputDrainer)
            assert drainer.is_running()
        finally:
            proc.kill()
            proc.wait(timeout=10)


class TestReadChildOutput:
    def test_returns_the_drained_tail(self):
        proc = _fake_child(
            "import sys;sys.stdout.write('boom: out of memory\\n');sys.stdout.flush()"
        )
        try:
            drainer = ChildOutputDrainer(proc.stdout, name="test")
            CPU_Engine._attach_output_drainer(proc, drainer)
            proc.wait(timeout=30)
            drainer.join(timeout=10)
            assert "boom: out of memory" in CPU_Engine._read_child_output(proc)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    def test_says_so_when_the_child_printed_nothing(self):
        proc = _fake_child("pass")
        try:
            drainer = ChildOutputDrainer(proc.stdout, name="test")
            CPU_Engine._attach_output_drainer(proc, drainer)
            proc.wait(timeout=30)
            drainer.join(timeout=10)
            assert "no output" in CPU_Engine._read_child_output(proc).lower()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    def test_handles_a_process_with_no_drainer(self):
        """Never raise out of the crash path just because the tail is missing."""
        assert isinstance(CPU_Engine._read_child_output(None), str)


class TestProbeReadyCrashMessage:
    def test_early_crash_message_carries_the_child_output(self, monkeypatch):
        """#361 + #360: the crash report must quote the child, not the logs."""
        proc = _fake_child(
            "import sys;sys.stdout.write('error loading model: bad magic\\n');sys.stdout.flush()"
        )
        drainer = ChildOutputDrainer(proc.stdout, name="test")
        CPU_Engine._attach_output_drainer(proc, drainer)
        proc.wait(timeout=30)
        drainer.join(timeout=10)

        with pytest.raises(EngineException) as excinfo:
            CPU_Engine._probe_ready(
                "http://127.0.0.1:1",  # never contacted: the dead child short-circuits
                proc=proc,
                model_field="alias",
            )
        assert "bad magic" in str(excinfo.value)
