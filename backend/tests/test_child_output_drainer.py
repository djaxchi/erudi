"""The `llama-server` child's output pipe must be drained for its whole life.

Regression tests for #361. A `subprocess.Popen` pipe is a fixed-size kernel
buffer: once it is full and nobody reads it, the child blocks in `write()` --
alive, silent, and making no progress. `llama-server` logs its startup banner,
the GGUF metadata dump, and a line per request, so an undrained pipe fills on
its own during a normal session.

`test_an_undrained_pipe_wedges_the_child` is the control: it proves the failure
mode is real on this machine and this OS, so the drained cases below are not
passing vacuously.
"""

import subprocess
import sys

import pytest

from src.engines.child_output import ChildOutputDrainer


# 1 MiB of output, far past any platform's pipe buffer (64 KiB measured on
# macOS; Windows pipes created with nSize=0 are typically smaller).
_LINE_PAYLOAD = "x" * 180
_LINES = 5000

_WRITER = (
    "import sys\n"
    f"for i in range({_LINES}):\n"
    f"    sys.stdout.write(f'line {{i}} {_LINE_PAYLOAD}\\n')\n"
    "sys.stdout.flush()\n"
)


def _spawn_writer() -> subprocess.Popen:
    """A child piped exactly the way `BaseLlamaCppEngine._spawn_child` pipes."""
    return subprocess.Popen(
        [sys.executable, "-c", _WRITER],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )


class TestUndrainedPipeIsTheBug:
    """The control: without a drainer the child never finishes."""

    def test_an_undrained_pipe_wedges_the_child(self):
        proc = _spawn_writer()
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                proc.wait(timeout=2.0)
            # Still alive, not crashed: blocked in write() on a full pipe.
            assert proc.poll() is None
        finally:
            proc.kill()
            proc.wait(timeout=10)


class TestDrainerUnblocksTheChild:
    def test_child_writing_past_the_pipe_buffer_runs_to_completion(self):
        proc = _spawn_writer()
        try:
            ChildOutputDrainer(proc.stdout, name="test-writer")
            assert proc.wait(timeout=30) == 0
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    def test_tail_holds_the_last_lines_written(self):
        proc = _spawn_writer()
        try:
            drainer = ChildOutputDrainer(proc.stdout, name="test-writer")
            assert proc.wait(timeout=30) == 0
            drainer.join(timeout=10)
            tail = drainer.tail()
            assert f"line {_LINES - 1} " in tail
            # ...and the beginning is gone: a tail, not the whole transcript.
            assert "line 0 " not in tail
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)


class TestTailShape:
    def test_tail_is_capped_in_characters(self):
        proc = _spawn_writer()
        try:
            drainer = ChildOutputDrainer(proc.stdout, name="test-writer")
            assert proc.wait(timeout=30) == 0
            drainer.join(timeout=10)
            assert len(drainer.tail(max_chars=500)) <= 500
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    def test_tail_keeps_only_the_configured_number_of_lines(self):
        proc = _spawn_writer()
        try:
            drainer = ChildOutputDrainer(proc.stdout, name="test-writer", tail_lines=5)
            assert proc.wait(timeout=30) == 0
            drainer.join(timeout=10)
            assert len(drainer.tail(max_chars=10_000).splitlines()) == 5
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    def test_tail_of_a_silent_child_is_empty(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        drainer = ChildOutputDrainer(proc.stdout, name="test-silent")
        assert proc.wait(timeout=30) == 0
        drainer.join(timeout=10)
        assert drainer.tail() == ""

    def test_tail_is_readable_before_the_child_exits(self):
        """The crash report must not have to wait for EOF to say something."""
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys,time;sys.stdout.write('hello\\n');sys.stdout.flush();time.sleep(30)",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        try:
            drainer = ChildOutputDrainer(proc.stdout, name="test-slow")
            assert drainer.wait_for_output(timeout=10) is True
            assert "hello" in drainer.tail()
        finally:
            proc.kill()
            proc.wait(timeout=10)

    def test_drainer_on_an_already_closed_stream_does_not_raise(self):
        """Shutdown races must not raise out of the reader thread."""
        proc = _spawn_writer()
        try:
            proc.stdout.close()
            drainer = ChildOutputDrainer(proc.stdout, name="test-writer")
            drainer.join(timeout=10)
            assert not drainer.is_running()
            assert drainer.tail() == ""
        finally:
            proc.kill()
            proc.wait(timeout=10)
