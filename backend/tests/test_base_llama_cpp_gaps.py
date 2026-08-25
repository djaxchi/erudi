"""Gap coverage for `BaseLlamaCppEngine` shared llama-server plumbing.

Complements `test_base_chat_server_engine.py` and the CPU/CUDA engine files:
binary resolution with the cross-flavour fallback, GGUF selection edge
cases (single file, unknown quants, mmproj exclusion), vision detection via
mmproj presence (#130), the Popen terminate/alive helpers, the spawn-child
handle assembly with the vision projector argv, and the default spawn env.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import EngineException
from src.engines import base_llama_cpp_engine as base_mod
from src.engines.cpu_engine import CPU_Engine


def _touch(path, size=16):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * size)
    return path


# =====================================================================
# UNIT - llama-server binary resolution
# =====================================================================

@pytest.mark.unit
class TestFindLlamaServer:

    def test_primary_flavour_wins(self, tmp_path):
        exe = "llama-server.exe" if os.name == "nt" else "llama-server"
        install = tmp_path / "cpu" / "bin"
        binary = _touch(install / exe)
        assert CPU_Engine._find_llama_server(install) == binary

    def test_falls_back_to_other_flavour(self, tmp_path, monkeypatch):
        exe = "llama-server.exe" if os.name == "nt" else "llama-server"
        monkeypatch.setattr(base_mod, "ROOT_DIR", tmp_path)
        cuda_binary = _touch(tmp_path / "artifacts" / "llama-cpp" / "cuda" / "bin" / exe)
        empty_cpu = tmp_path / "artifacts" / "llama-cpp" / "cpu" / "bin"
        empty_cpu.mkdir(parents=True)
        assert CPU_Engine._find_llama_server(empty_cpu) == cuda_binary

    def test_missing_everywhere_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(base_mod, "ROOT_DIR", tmp_path)
        install = tmp_path / "nothing" / "bin"
        install.mkdir(parents=True)
        with pytest.raises(EngineException, match="llama-server binary not found"):
            CPU_Engine._find_llama_server(install)


# =====================================================================
# UNIT - GGUF selection edge cases
# =====================================================================

@pytest.mark.unit
class TestSelectGgufEdgeCases:

    def test_missing_path_raises(self, tmp_path):
        with pytest.raises(EngineException, match="not found"):
            CPU_Engine._select_gguf(tmp_path / "missing")

    def test_single_gguf_in_directory(self, tmp_path):
        only = _touch(tmp_path / "model-exotic.gguf")
        assert CPU_Engine._select_gguf(tmp_path) == only

    def test_mmproj_files_never_selected(self, tmp_path):
        model = _touch(tmp_path / "model-q4_k_m.gguf")
        _touch(tmp_path / "mmproj-model-f16.gguf")
        assert CPU_Engine._select_gguf(tmp_path) == model

    def test_unknown_quants_pick_smallest(self, tmp_path):
        _touch(tmp_path / "model-alpha.gguf", size=4096)
        small = _touch(tmp_path / "model-beta.gguf", size=64)
        assert CPU_Engine._select_gguf(tmp_path) == small


# =====================================================================
# UNIT - vision detection via mmproj (#130)
# =====================================================================

@pytest.mark.unit
class TestVisionDetection:

    def test_find_mmproj_none(self, tmp_path):
        model = _touch(tmp_path / "model-q4_k_m.gguf")
        assert CPU_Engine._find_mmproj(model) is None

    def test_find_mmproj_multiple_picks_first(self, tmp_path):
        model = _touch(tmp_path / "model-q4_k_m.gguf")
        _touch(tmp_path / "mmproj-a.gguf")
        _touch(tmp_path / "mmproj-b.gguf")
        found = CPU_Engine._find_mmproj(model)
        assert found is not None
        assert found.name.startswith("mmproj-")

    def test_model_supports_vision_true(self, tmp_path):
        _touch(tmp_path / "model-q4_k_m.gguf")
        _touch(tmp_path / "mmproj-model.gguf")
        assert CPU_Engine.model_supports_vision(tmp_path) is True

    def test_model_supports_vision_false(self, tmp_path):
        _touch(tmp_path / "model-q4_k_m.gguf")
        assert CPU_Engine.model_supports_vision(tmp_path) is False

    def test_model_supports_vision_unreadable_is_none(self, tmp_path):
        assert CPU_Engine.model_supports_vision(tmp_path / "missing") is None


# =====================================================================
# UNIT - Popen lifecycle helpers
# =====================================================================

@pytest.mark.unit
class TestProcessHelpers:

    def test_terminate_none_is_noop(self):
        CPU_Engine._terminate_process(None)

    def test_terminate_already_exited_is_noop(self):
        proc = MagicMock()
        proc.poll.return_value = 0
        CPU_Engine._terminate_process(proc)
        proc.send_signal.assert_not_called()
        proc.terminate.assert_not_called()

    def test_terminate_running_posix_sends_sigint(self):
        import signal as signal_mod

        proc = MagicMock()
        proc.poll.return_value = None
        with patch.object(base_mod.platform, "system", return_value="Linux"):
            CPU_Engine._terminate_process(proc)
        proc.send_signal.assert_called_once_with(signal_mod.SIGINT)
        proc.wait.assert_called_once()
        proc.kill.assert_not_called()

    def test_terminate_running_windows_uses_terminate(self):
        proc = MagicMock()
        proc.poll.return_value = None
        with patch.object(base_mod.platform, "system", return_value="Windows"):
            CPU_Engine._terminate_process(proc)
        proc.terminate.assert_called_once()

    def test_terminate_escalates_to_kill_on_stuck_wait(self):
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = TimeoutError("still alive")
        with patch.object(base_mod.platform, "system", return_value="Linux"):
            CPU_Engine._terminate_process(proc)
        proc.kill.assert_called_once()

    def test_terminate_swallows_poll_failure(self):
        proc = MagicMock()
        proc.poll.side_effect = OSError("gone")
        CPU_Engine._terminate_process(proc)  # best effort, no raise

    def test_proc_is_alive_matrix(self):
        assert CPU_Engine._proc_is_alive(None) is False
        running = MagicMock()
        running.poll.return_value = None
        assert CPU_Engine._proc_is_alive(running) is True
        exited = MagicMock()
        exited.poll.return_value = 1
        assert CPU_Engine._proc_is_alive(exited) is False
        broken = MagicMock()
        broken.poll.side_effect = OSError("gone")
        assert CPU_Engine._proc_is_alive(broken) is False


# =====================================================================
# UNIT - spawn-child handle assembly
# =====================================================================

@pytest.mark.unit
class TestSpawnChild:

    def _spawn(self, tmp_path, monkeypatch, *, with_mmproj):
        model = _touch(tmp_path / "model-q4_k_m.gguf")
        if with_mmproj:
            _touch(tmp_path / "mmproj-model.gguf")
        server = _touch(tmp_path / "bin" / "llama-server")
        monkeypatch.setattr(
            CPU_Engine, "_find_llama_server", classmethod(lambda cls, d=None: server)
        )
        captured = {}

        def fake_popen(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            # `stdout` is part of the Popen contract `_spawn_child` relies on:
            # it creates the child with stdout=PIPE and hands the stream to the
            # output drainer (#361). None here means "this test captures no
            # output", which the drainer accepts as a no-op.
            return SimpleNamespace(pid=4242, stdout=None)

        monkeypatch.setattr(base_mod.subprocess, "Popen", fake_popen)
        handle = CPU_Engine._spawn_child(
            model_path=model, alias="erudi-1", port=27201,
            **CPU_Engine._prepare_spawn_context(),
        )
        return handle, captured

    def test_handle_carries_context_and_base_url(self, tmp_path, monkeypatch):
        handle, captured = self._spawn(tmp_path, monkeypatch, with_mmproj=False)
        assert handle["pid"] == 4242
        assert handle["port"] == 27201
        assert handle["base_url"] == "http://127.0.0.1:27201"
        assert handle["alias"] == "erudi-1"
        assert handle["gpu_layers"] == 0  # CPU context preserved for observability
        assert handle["threads"] >= 1
        assert "--mmproj" not in captured["argv"]

    def test_mmproj_is_appended_to_argv(self, tmp_path, monkeypatch):
        _handle, captured = self._spawn(tmp_path, monkeypatch, with_mmproj=True)
        argv = captured["argv"]
        assert "--mmproj" in argv
        assert argv[argv.index("--mmproj") + 1].endswith("mmproj-model.gguf")

    def test_default_spawn_env_inherits_parent(self):
        env = CPU_Engine._build_spawn_env()
        assert env == os.environ.copy()
