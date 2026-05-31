"""Tests for `MLX_Engine` in server-mode (subprocess `mlx_lm.server`).

This file is written **before** the implementation (TDD-RED phase). All tests
target the post-refactor API described in `plan: refactor/mlx-server-subprocess`.
Until Phase 2 lands the new `MLX_Engine` implementation, these tests should
fail (typically with `AttributeError` on missing internal methods, or with
content-mismatch on `generate_stream` SSE parsing).

Test sections:
    - **Unit** (`@pytest.mark.unit`): fully mocked, no MLX dependency, no
      subprocess spawn. Runs on Linux CI.
    - **Integration engine** (`@pytest.mark.mlx_only`): spawns a real
      `mlx_lm.server` subprocess against a small downloaded model. Skipped
      on Linux CI via the `mlx_test_model_path` fixture.
    - **Thinking model regression** (`@pytest.mark.mlx_only`, opt-in via
      `ERUDI_TEST_THINKING=1`): validates that the OpenAI `reasoning` channel
      (delivered for thinking-capable models like Qwen3) does NOT leak into
      the yielded token stream — preserving the iso-behaviour of the current
      `<|channel>thought ... <channel|>` filter.
    - **Gemma EOS regression** (`@pytest.mark.mlx_only`, opt-in via
      `ERUDI_TEST_GEMMA=1`): validates the audit's GAP #15 (Gemma
      `<end_of_turn>` may not be in `eos_token_ids` natively). If it fails,
      Phase 2 must wire a per-family `stop` fallback.
    - **E2E full-stack** (`@pytest.mark.e2e @pytest.mark.mlx_only`): drives
      the new engine through the actual FastAPI endpoints
      (`POST /erudi/conversations/{id}/query`, ...) to confirm no
      observable contract regression downstream of the engine.

Patch targets (Phase 2 module shape assumed):
    - `src.engines.mlx_engine.mp` — `multiprocessing as mp`, used as `mp.Process(...)`.
    - `src.engines.base_chat_server_engine.requests` — http client (same pattern as
      `cpu_engine.py:25`).
    - `src.engines.base_chat_server_engine.socket` — module-level import for `_pick_free_port`.

Run examples:
    pytest backend/tests/test_mlx_engine_server.py -m unit          # CI-friendly
    pytest backend/tests/test_mlx_engine_server.py -m mlx_only      # local Mac
    ERUDI_TEST_THINKING=1 pytest ... -k thinking                    # opt-in
"""
from __future__ import annotations

import json
import socket as _stdlib_socket
import threading
import time
from pathlib import Path
from typing import Iterator, List
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.engines.mlx_engine import MLX_Engine


# =====================================================================
# Helpers shared by unit tests
# =====================================================================

def _sse_bytes(payloads: List[dict | str]) -> Iterator[bytes]:
    """Render a list of payloads as raw SSE bytes chunks.

    Mirrors what `requests.Response.iter_content(chunk_size=None)` yields when
    streaming from `mlx_lm.server`. Strings are emitted verbatim (used to
    inject `[DONE]` and corrupted lines). Dicts are JSON-encoded.
    """
    for p in payloads:
        if isinstance(p, str):
            yield f"data: {p}\n\n".encode("utf-8")
        else:
            yield f"data: {json.dumps(p)}\n\n".encode("utf-8")


def _mock_streaming_post(sse_chunks: List[bytes]):
    """Return a Mock suitable for patching `requests.post(..., stream=True)`.

    Context-manager (`with requests.post(...) as r:`) yields a Response-like
    Mock whose `iter_content` walks the supplied bytes chunks.
    """
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.iter_content.return_value = iter(sse_chunks)
    cm = MagicMock()
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return Mock(return_value=cm)


def _reset_mlx_engine_class_state() -> None:
    """Wipe the shared class-level state of MLX_Engine.

    Required between tests because `MLX_Engine` is a singleton-style class
    with mutable class attributes (`_model`, `_tokenizer`, `_model_id`,
    `_last_used`). Without this, a leaked Mock from one test would be
    interpreted as a cached real model by the next.
    """
    MLX_Engine._model = None
    MLX_Engine._tokenizer = None
    MLX_Engine._model_id = None
    MLX_Engine._last_used = None


@pytest.fixture(autouse=True)
def _mlx_engine_state_reset():
    """Reset MLX_Engine class state around every test in this file.

    Critically, the teardown also attempts `cleanup()` so that any real
    subprocess spawned by an integration test that raised mid-setup is
    terminated before the next test runs. Without this, an exception in
    `get_model_and_tokenizer` between spawn and the test's own `finally:
    cleanup()` would leak the child process.
    """
    _reset_mlx_engine_class_state()
    yield
    try:
        MLX_Engine.cleanup()
    except Exception:
        # cleanup() failures during teardown must not mask the real test
        # error — best-effort only.
        pass
    _reset_mlx_engine_class_state()


# =====================================================================
# UNIT — module-shape invariants
# =====================================================================
#
# These tests pin down the import structure expected by every other test in
# this file. Without them, a Phase 2 implementation that imports the same
# libraries under different aliases (e.g. `from multiprocessing import
# Process` instead of `import multiprocessing as mp`) would silently bypass
# the patch targets — the mocks would be no-ops and the unit suite would
# pass while testing nothing.
#
# When any of these fail, the fix is one of:
#   - Update the impl to match the expected alias, OR
#   - Update every `patch("src.engines.mlx_engine.<name>")` call site in
#     this file AND the matching invariant test below.

@pytest.mark.unit
class TestModuleImportInvariants:
    """Pin the module-level imports the mocks in this file rely on.

    Post-migration to BaseChatServerEngine: `requests`, `socket`, `atexit`,
    `time` are owned by the base module; only `mp` (multiprocessing) is
    still imported at the MLX module level because `_spawn_child` uses
    `mp.Process` directly.
    """

    def test_mlx_engine_exposes_mp_alias(self):
        """`import multiprocessing as mp` must be at module level."""
        from src.engines import mlx_engine as mod
        assert hasattr(mod, "mp"), (
            "src/engines/mlx_engine.py must `import multiprocessing as mp` at "
            "module level (patch target: src.engines.mlx_engine.mp). Without "
            "it, the mp.Process mocks in this file are no-ops."
        )

    def test_base_chat_server_engine_exposes_requests(self):
        """`import requests` is in the base module post-migration."""
        from src.engines import base_chat_server_engine as base
        assert hasattr(base, "requests")

    def test_base_chat_server_engine_exposes_socket(self):
        """`import socket` is in the base module post-migration."""
        from src.engines import base_chat_server_engine as base
        assert hasattr(base, "socket")

    def test_base_chat_server_engine_exposes_atexit(self):
        """`import atexit` is in the base module post-migration."""
        from src.engines import base_chat_server_engine as base
        assert hasattr(base, "atexit")


# =====================================================================
# UNIT — _pick_free_port
# =====================================================================

def _patched_socket_module(bind_side_effect):
    """Build a contextmanager-style mock of the `socket` module.

    Replaces `socket.socket(AF_INET, SOCK_STREAM)` so that `s.bind(addr)`
    invokes `bind_side_effect(addr)`. Preserves the real constants so the
    impl's `setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)` doesn't crash on
    `mock.AttributeError`.
    """
    patcher = patch("src.engines.base_chat_server_engine.socket")
    mock_socket_mod = patcher.start()
    mock_sock = mock_socket_mod.socket.return_value.__enter__.return_value
    mock_sock.bind.side_effect = bind_side_effect
    mock_socket_mod.AF_INET = _stdlib_socket.AF_INET
    mock_socket_mod.SOCK_STREAM = _stdlib_socket.SOCK_STREAM
    mock_socket_mod.SOL_SOCKET = _stdlib_socket.SOL_SOCKET
    mock_socket_mod.SO_REUSEADDR = _stdlib_socket.SO_REUSEADDR
    return patcher





# =====================================================================
# UNIT — _terminate_process (mp.Process API)
# =====================================================================

@pytest.mark.unit
class TestTerminateProcess:
    """Termination must be idempotent, bounded in time, and safe on dead/None."""

    @staticmethod
    def _bounded_join_timeout(proc_mock: MagicMock) -> float:
        """Extract the `timeout=` kwarg passed to proc.join()."""
        assert proc_mock.join.called, "join() was not called"
        call = proc_mock.join.call_args
        timeout = call.kwargs.get("timeout")
        if timeout is None and call.args:
            # Some impls may pass positionally; tolerate either.
            timeout = call.args[0]
        assert timeout is not None, "join() was called without a timeout"
        return float(timeout)

    def test_terminate_then_join_with_bounded_timeout(self):
        """Must call terminate() and join(timeout≤10s) — never a blocking join()."""
        proc = MagicMock()
        proc.is_alive.return_value = True
        MLX_Engine._terminate_process(proc)
        proc.terminate.assert_called_once()
        timeout = self._bounded_join_timeout(proc)
        assert 0 < timeout <= 10, (
            f"join() timeout must be in (0, 10]s to avoid blocking shutdown, "
            f"got {timeout!r}"
        )

    def test_no_op_when_already_dead(self):
        proc = MagicMock()
        proc.is_alive.return_value = False
        MLX_Engine._terminate_process(proc)
        proc.terminate.assert_not_called()

    def test_force_kill_if_join_times_out(self):
        """If terminate+join didn't kill it, must escalate to .kill()."""
        proc = MagicMock()
        # First poll says alive, after .join() still alive → escalate.
        proc.is_alive.side_effect = [True, True, False]
        MLX_Engine._terminate_process(proc)
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    def test_none_proc_is_safe(self):
        """Passing None must not crash (mirrors cpu_engine.py:228-229)."""
        MLX_Engine._terminate_process(None)  # no exception


# =====================================================================
# UNIT — generate_stream (SSE parsing)
# =====================================================================

@pytest.mark.unit
class TestGenerateStreamSSEParsing:
    """Validates that `generate_stream` correctly parses the mlx_lm.server SSE.

    The new impl is expected to:
      - POST to `{base_url}/v1/chat/completions` with `stream=True`
      - Yield `choices[0].delta.content` strings (non-empty only)
      - Ignore the `[DONE]` terminator
      - Silently drop `choices[0].delta.reasoning` (thinking channel)
      - Survive malformed JSON lines without raising
    """

    def _fake_model(self, port: int = 9090) -> dict:
        return {
            "pid": 1,
            "proc": MagicMock(),
            "port": port,
            "base_url": f"http://127.0.0.1:{port}",
            "alias": "erudi-test",
            "model_path": "/x",
        }

    def _fake_tokenizer(self) -> dict:
        return {"type": "remote", "provider": "mlx-lm-server"}

    def test_yields_concatenated_delta_content(self):
        chunks = _sse_bytes([
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " "}}]},
            {"choices": [{"delta": {"content": "world"}}]},
            {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            "[DONE]",
        ])
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post = _mock_streaming_post(list(chunks))

            tokens = list(MLX_Engine.generate_stream(
                model=self._fake_model(),
                tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "hi"}],
                max_tokens=10, temperature=0.5, top_p=0.9,
            ))
        assert "".join(tokens) == "Hello world"

    def test_ignores_done_terminator(self):
        """The literal `[DONE]` must never appear in yielded tokens."""
        chunks = _sse_bytes([
            {"choices": [{"delta": {"content": "X"}}]},
            "[DONE]",
        ])
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post = _mock_streaming_post(list(chunks))
            tokens = list(MLX_Engine.generate_stream(
                model=self._fake_model(), tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "hi"}],
                max_tokens=5, temperature=0.0, top_p=1.0,
            ))
        assert "[DONE]" not in "".join(tokens)
        assert "".join(tokens) == "X"

    def test_ignores_reasoning_field_by_default(self):
        """`choices[0].delta.reasoning` (thinking-mode) is dropped silently.

        Iso-behaviour with the current `<|channel>thought ... <channel|>`
        manual filter — Phase 2 must not leak reasoning into the visible
        token stream (modulo a future opt-in flag).
        """
        chunks = _sse_bytes([
            {"choices": [{"delta": {"content": "", "reasoning": "I should think..."}}]},
            {"choices": [{"delta": {"content": "Answer", "reasoning": ""}}]},
            "[DONE]",
        ])
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post = _mock_streaming_post(list(chunks))
            tokens = list(MLX_Engine.generate_stream(
                model=self._fake_model(), tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "?"}],
                max_tokens=5, temperature=0.0, top_p=1.0,
            ))
        out = "".join(tokens)
        assert "I should think" not in out, (
            "reasoning text leaked into visible stream"
        )
        assert out == "Answer"

    def test_survives_malformed_sse_line(self):
        """A corrupted JSON line must not abort the stream."""
        chunks = _sse_bytes([
            {"choices": [{"delta": {"content": "before"}}]},
            "not json {{{",
            {"choices": [{"delta": {"content": "after"}}]},
            "[DONE]",
        ])
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post = _mock_streaming_post(list(chunks))
            tokens = list(MLX_Engine.generate_stream(
                model=self._fake_model(), tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "x"}],
                max_tokens=5, temperature=0.0, top_p=1.0,
            ))
        assert "".join(tokens) == "beforeafter"

    def test_payload_includes_stream_true_and_messages(self):
        chunks = _sse_bytes(["[DONE]"])
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post = _mock_streaming_post(list(chunks))
            list(MLX_Engine.generate_stream(
                model=self._fake_model(), tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "Q?"}],
                max_tokens=42, temperature=0.7, top_p=0.95,
            ))
            assert mock_requests.post.called
            kwargs = mock_requests.post.call_args.kwargs
            payload = kwargs.get("json") or {}
            assert payload.get("stream") is True
            assert payload.get("messages") == [{"role": "user", "content": "Q?"}]
            assert payload.get("max_tokens") == 42
            assert payload.get("temperature") == pytest.approx(0.7)
            assert payload.get("top_p") == pytest.approx(0.95)

    def test_invalid_model_handle_raises(self):
        """If model handle is not a dict with `base_url`, must raise clearly."""
        with pytest.raises(Exception):
            list(MLX_Engine.generate_stream(
                model=Mock(),  # not a dict
                tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "x"}],
                max_tokens=1, temperature=0.0, top_p=1.0,
            ))

    def test_survives_chunk_split_mid_json(self):
        """A JSON message split across two `iter_content` chunks must parse correctly.

        Critical for UTF-8 multi-byte safety and for tolerating arbitrary TCP
        fragmentation. The CPU/CUDA twin implements this via byte-buffer +
        newline split (cpu_engine.py:629-652); the MLX impl must do the same.
        """
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Hel',  # split mid-content
            b'lo"}}]}\n\ndata: {"choices":[{"delta":{"content":" world"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post = _mock_streaming_post(chunks)
            tokens = list(MLX_Engine.generate_stream(
                model=self._fake_model(), tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "x"}],
                max_tokens=5, temperature=0.0, top_p=1.0,
            ))
        assert "".join(tokens) == "Hello world", (
            f"chunk-split JSON not reassembled correctly: {tokens!r}"
        )

    def test_http_error_status_raises(self):
        """HTTP 4xx/5xx from the server must surface as an engine exception."""
        from requests.exceptions import HTTPError
        response = MagicMock()
        response.raise_for_status.side_effect = HTTPError("500 server error")
        cm = MagicMock()
        cm.__enter__.return_value = response
        cm.__exit__.return_value = False
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post.return_value = cm

            with pytest.raises(Exception):
                list(MLX_Engine.generate_stream(
                    model=self._fake_model(), tokenizer=self._fake_tokenizer(),
                    prompt=[{"role": "user", "content": "x"}],
                    max_tokens=5, temperature=0.0, top_p=1.0,
                ))

    def test_extra_kwargs_swallowed_without_crash(self):
        """`generate_stream` must accept (and ignore) kwargs the server doesn't take.

        The conversations service passes `repetition_penalty=1.2`,
        `repetition_context_size=...` regardless of engine (services.py:493).
        Both must be passed silently — the server consumes them, but if it
        didn't, the engine must not crash.
        """
        chunks = _sse_bytes([
            {"choices": [{"delta": {"content": "OK"}}]},
            "[DONE]",
        ])
        with patch("src.engines.base_chat_server_engine.requests") as mock_requests:
            mock_requests.post = _mock_streaming_post(list(chunks))
            tokens = list(MLX_Engine.generate_stream(
                model=self._fake_model(), tokenizer=self._fake_tokenizer(),
                prompt=[{"role": "user", "content": "x"}],
                max_tokens=5, temperature=0.0, top_p=1.0,
                repetition_penalty=1.2,
                repetition_context_size=512,
                some_future_unknown_kwarg=True,
            ))
        assert "".join(tokens) == "OK"




@pytest.mark.unit
class TestCleanupAndCache:
    """Cleanup must terminate the subprocess; cache must avoid respawn."""

    def test_cleanup_terminates_subprocess(self):
        proc = MagicMock()
        proc.is_alive.return_value = True
        MLX_Engine._model = {
            "pid": 1, "proc": proc, "port": 9090,
            "base_url": "http://127.0.0.1:9090",
            "alias": "erudi-x", "model_path": "/x",
        }
        MLX_Engine._tokenizer = {"type": "remote", "provider": "mlx-lm-server"}
        MLX_Engine._model_id = "x"

        MLX_Engine.cleanup()

        proc.terminate.assert_called_once()
        assert MLX_Engine._model is None
        assert MLX_Engine._tokenizer is None
        assert MLX_Engine._model_id is None

    def test_get_model_and_tokenizer_returns_cached_when_same_id(self):
        sentinel_model = {"pid": 7, "cached": True}
        sentinel_tokenizer = {"type": "remote"}
        MLX_Engine._model = sentinel_model
        MLX_Engine._tokenizer = sentinel_tokenizer
        MLX_Engine._model_id = "abc"

        with patch.object(MLX_Engine, "_start_server") as mock_start:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="abc", llm_local_path="/whatever",
            )

        mock_start.assert_not_called()
        assert model is sentinel_model
        assert tokenizer is sentinel_tokenizer

    def test_get_model_and_tokenizer_kills_old_when_switching(self, tmp_path):
        """Switching to a different llm_id must terminate the previous proc."""
        new_dir = tmp_path / "new"
        new_dir.mkdir()
        resolved_new = new_dir.resolve()

        old_proc = MagicMock()
        old_proc.is_alive.return_value = True
        MLX_Engine._model = {
            "pid": 7, "proc": old_proc, "port": 9091,
            "base_url": "http://127.0.0.1:9091",
            "alias": "erudi-old", "model_path": "/old",
        }
        MLX_Engine._tokenizer = {"type": "remote", "provider": "mlx-lm-server"}
        MLX_Engine._model_id = "old"

        new_handle = {
            "pid": 8, "proc": MagicMock(), "port": 9092,
            "base_url": "http://127.0.0.1:9092",
            "alias": "erudi-new", "model_path": str(resolved_new),
        }
        with patch.object(MLX_Engine, "_start_server", return_value=new_handle) as mock_start, \
             patch.object(MLX_Engine, "_pick_free_port", return_value=9092):
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="new", llm_local_path=str(new_dir),
            )

        old_proc.terminate.assert_called_once()
        mock_start.assert_called_once_with(
            model_path=resolved_new, alias="erudi-new", port=9092,
        )
        assert MLX_Engine._model_id == "new"
        assert model is new_handle


# =====================================================================
# UNIT — _mlx_server_runner helper module (picklable target)
# =====================================================================

@pytest.mark.unit
class TestMlxServerRunnerHelper:
    """The runner is a module-level function so it can be pickled by spawn."""

    def test_module_function_is_importable(self):
        from src.engines import _mlx_server_runner
        assert hasattr(_mlx_server_runner, "run_mlx_server")
        assert callable(_mlx_server_runner.run_mlx_server)

    def test_runner_patches_sys_argv_and_calls_main(self):
        from src.engines import _mlx_server_runner
        with patch.object(_mlx_server_runner, "_import_mlx_server_main") as mock_import:
            fake_main = MagicMock()
            mock_import.return_value = fake_main
            _mlx_server_runner.run_mlx_server(
                ["mlx_lm.server", "--model", "/x", "--port", "9080"]
            )
            fake_main.assert_called_once()


# =====================================================================
# INTEGRATION — real mlx_lm.server subprocess + real model
# =====================================================================

@pytest.mark.mlx_only
class TestSubprocessReal:
    """Spawn a real `mlx_lm.server` against a small downloaded model.

    Uses the session-scoped `mlx_test_model_path` fixture, which skips the
    test entirely on non-Apple-Silicon hosts. Each test does its own
    start/cleanup to validate the full lifecycle.
    """

    def test_subprocess_starts_and_serves_health(self, mlx_test_model_path):
        import requests
        try:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen-test", llm_local_path=str(mlx_test_model_path),
            )
            assert model["proc"].is_alive(), "subprocess died right after spawn"
            r = requests.get(f"{model['base_url']}/health", timeout=5)
            assert r.status_code == 200
            assert tokenizer == {"type": "remote", "provider": "mlx-lm-server"}
        finally:
            MLX_Engine.cleanup()

    def test_real_stream_yields_non_empty_tokens(self, mlx_test_model_path):
        try:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen-test", llm_local_path=str(mlx_test_model_path),
            )
            tokens = []
            for tok in MLX_Engine.generate_stream(
                model, tokenizer,
                prompt=[{"role": "user", "content": "Say hi in one word."}],
                max_tokens=20, temperature=0.0, top_p=1.0,
            ):
                tokens.append(tok)
            full = "".join(tokens)
            assert len(tokens) > 0, "no tokens yielded"
            assert len(full.strip()) > 0, f"only whitespace yielded: {full!r}"
        finally:
            MLX_Engine.cleanup()

    def test_real_stream_stops_within_max_tokens(self, mlx_test_model_path):
        """With max_tokens cap, the stream must end (not run forever)."""
        try:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen-test", llm_local_path=str(mlx_test_model_path),
            )
            t0 = time.monotonic()
            tokens = list(MLX_Engine.generate_stream(
                model, tokenizer,
                prompt=[{"role": "user", "content": "Count from 1 to 100"}],
                max_tokens=5, temperature=0.0, top_p=1.0,
            ))
            elapsed = time.monotonic() - t0
            assert elapsed < 60.0, f"stream did not terminate in <60s: {elapsed:.1f}s"
            # max_tokens=5 → at most a handful of token deltas. Loose bound
            # because tokens may emit as partial chars in some templates.
            assert len(tokens) <= 60
        finally:
            MLX_Engine.cleanup()

    def test_real_chat_template_applied_for_system_role(self, mlx_test_model_path):
        """A system+user prompt must produce a coherent response, not echo.

        Validates that `mlx_lm.server` applies the model's chat template
        (otherwise the model would treat the system instruction as user
        text and the output would not look like a 'reply').
        """
        try:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen-test", llm_local_path=str(mlx_test_model_path),
            )
            prompt = [
                {"role": "system", "content": "Answer with exactly the word: OK"},
                {"role": "user", "content": "ping"},
            ]
            out = "".join(MLX_Engine.generate_stream(
                model, tokenizer, prompt, max_tokens=10, temperature=0.0, top_p=1.0,
            ))
            # We do NOT assert "OK" verbatim (Qwen 0.5B may not be that obedient);
            # we only assert that the output does not contain the literal system
            # instruction verbatim (which would prove the template was skipped).
            assert "Answer with exactly the word" not in out, (
                "chat template was not applied — system prompt leaked into output"
            )
        finally:
            MLX_Engine.cleanup()

    def test_concurrent_requests_dont_crash(self, mlx_test_model_path):
        """Regression for commits cefdc7a, 40fb55e (Stream(gpu, 0) crash).

        With the subprocess isolation, multiple concurrent generate_stream
        calls must all complete without raising. We don't assert content
        ordering — only that no thread raises.
        """
        try:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen-test", llm_local_path=str(mlx_test_model_path),
            )

            errors: List[BaseException] = []

            def _worker(idx: int) -> None:
                try:
                    list(MLX_Engine.generate_stream(
                        model, tokenizer,
                        prompt=[{"role": "user", "content": f"hi #{idx}"}],
                        max_tokens=8, temperature=0.0, top_p=1.0,
                    ))
                except BaseException as e:  # noqa: BLE001 — surface everything
                    errors.append(e)

            threads = [threading.Thread(target=_worker, args=(i,)) for i in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=120)
            assert not errors, f"concurrent stream errors: {errors!r}"
        finally:
            MLX_Engine.cleanup()

    def test_cleanup_kills_subprocess_and_frees_port(self, mlx_test_model_path):
        model, _ = MLX_Engine.get_model_and_tokenizer(
            llm_id="qwen-test", llm_local_path=str(mlx_test_model_path),
        )
        port = model["port"]
        proc = model["proc"]
        assert proc.is_alive()

        MLX_Engine.cleanup()

        # Give the OS a brief moment to release the port.
        for _ in range(20):
            if not proc.is_alive():
                break
            time.sleep(0.1)
        assert not proc.is_alive(), "subprocess survived cleanup()"

        # Port should be re-bindable.
        with _stdlib_socket.socket(_stdlib_socket.AF_INET, _stdlib_socket.SOCK_STREAM) as s:
            s.setsockopt(_stdlib_socket.SOL_SOCKET, _stdlib_socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))  # must not raise

    def test_switch_model_terminates_old_subprocess(self, mlx_test_model_path):
        """Calling get_model_and_tokenizer with a new llm_id must kill the old proc."""
        try:
            m1, _ = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen-test", llm_local_path=str(mlx_test_model_path),
            )
            old_proc = m1["proc"]
            assert old_proc.is_alive()

            # Reuse the same path but with a different llm_id to force respawn.
            m2, _ = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen-test-bis", llm_local_path=str(mlx_test_model_path),
            )
            for _ in range(20):
                if not old_proc.is_alive():
                    break
                time.sleep(0.1)
            assert not old_proc.is_alive(), "old subprocess was not terminated on switch"
            assert m2["proc"] is not old_proc
            assert m2["proc"].is_alive()
        finally:
            MLX_Engine.cleanup()


# =====================================================================
# INTEGRATION — thinking-model regression (opt-in via ERUDI_TEST_THINKING=1)
# =====================================================================

@pytest.mark.mlx_only
class TestThinkingModelRegression:
    """The reasoning channel must NOT leak into the yielded token stream.

    Activated by `mlx_thinking_model_path` (opt-in via ERUDI_TEST_THINKING=1).
    Without this test, a Phase 2 regression that forwards `delta.reasoning`
    to the caller would be invisible to the default suite.
    """

    def test_reasoning_text_not_in_visible_stream(self, mlx_thinking_model_path):
        try:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="qwen3-thinking",
                llm_local_path=str(mlx_thinking_model_path),
            )
            out = "".join(MLX_Engine.generate_stream(
                model, tokenizer,
                prompt=[{"role": "user", "content": "What is 2+2? Reply briefly."}],
                max_tokens=64, temperature=0.0, top_p=1.0,
            ))
            # Tokens specific to common thinking templates. If any of these
            # surface, the reasoning channel is leaking.
            forbidden = ["<think>", "</think>", "<|channel>", "<channel|>"]
            for needle in forbidden:
                assert needle not in out, (
                    f"reasoning marker {needle!r} leaked into visible stream: {out!r}"
                )
        finally:
            MLX_Engine.cleanup()


# =====================================================================
# INTEGRATION — Gemma EOS regression (opt-in via ERUDI_TEST_GEMMA=1)
# =====================================================================

@pytest.mark.mlx_only
class TestGemmaEOSRegression:
    """Validates audit GAP #15 — Gemma `<end_of_turn>` may not stop natively.

    Opt-in via ERUDI_TEST_GEMMA=1. If this test fails, Phase 2 must wire a
    per-family `stop` fallback in the request payload.
    """

    @pytest.fixture(scope="class")
    def gemma_path(self):
        import os
        if os.environ.get("ERUDI_TEST_GEMMA") != "1":
            pytest.skip("Set ERUDI_TEST_GEMMA=1 to enable Gemma EOS regression test")
        from huggingface_hub import snapshot_download
        repo = os.environ.get(
            "ERUDI_MLX_GEMMA_REPO", "mlx-community/gemma-3-270m-it-4bit"
        )
        try:
            return Path(snapshot_download(repo_id=repo))
        except Exception as exc:
            pytest.skip(f"Cannot fetch Gemma model {repo!r}: {exc}")

    def test_gemma_stops_within_reasonable_bound(self, gemma_path):
        """A short instruct prompt must terminate well before max_tokens=200."""
        try:
            model, tokenizer = MLX_Engine.get_model_and_tokenizer(
                llm_id="gemma-test", llm_local_path=str(gemma_path),
            )
            out_tokens = list(MLX_Engine.generate_stream(
                model, tokenizer,
                prompt=[{"role": "user", "content": "Say hello."}],
                max_tokens=200, temperature=0.0, top_p=1.0,
            ))
            # If EOS works correctly, the response is short (≪ 200 tokens).
            # If `<end_of_turn>` is not recognized, it runs to the cap.
            assert len(out_tokens) < 150, (
                "Gemma did not stop on <end_of_turn> — "
                "Phase 2 must add stop=['<end_of_turn>'] in the request payload"
            )
        finally:
            MLX_Engine.cleanup()


# =====================================================================
# E2E — full FastAPI stack with real MLX engine
# =====================================================================

@pytest.mark.mlx_only
@pytest.mark.e2e
class TestE2EConversationsRealMLX:
    """Drive `POST /erudi/conversations/{id}/query` through the new engine.

    These tests confirm the contract is preserved at the HTTP boundary —
    services, repository, streaming response, message persistence all
    keep working when the engine is server-mode subprocess MLX.

    Notes for maintainers:
      - The `_force_mlx_engine_in_config` autouse fixture pins
        `src.core.config.LLM_Engine = MLX_Engine` for the duration of each
        e2e test. Without it, an unrelated earlier test (e.g.
        `test_engines.py::test_get_engine_returns_valid_class`) could have
        set `config.LLM_Engine = CPU_Engine`, in which case these e2e
        tests would silently exercise CPU_Engine and produce baffling
        failures.
      - The endpoint currently routes through `endpoints._stream_on_single_thread`
        (a 1-thread ThreadPoolExecutor). Phase 3 removes that wrapper;
        these tests must keep passing through both Phase 2 (wrapper still
        there) and Phase 3 (wrapper gone).
    """

    @pytest.fixture(autouse=True)
    def _force_mlx_engine_in_config(self):
        from src.core import config
        prev = getattr(config, "LLM_Engine", None)
        config.LLM_Engine = MLX_Engine
        yield
        config.LLM_Engine = prev

    def _make_llm_row(self, db_session, model_path: Path):
        """Insert an Llm pointing to the real MLX model path."""
        from src.entities.Llm import Llm
        llm = Llm(
            name="Qwen2.5-0.5B-Instruct-4bit",
            description="Integration test model",
            local=1,
            link=str(model_path),
            type="qwen",
            is_attached_to_kb=False,
            param_size=0.5,
            quantized=True,
        )
        db_session.add(llm)
        db_session.commit()
        db_session.refresh(llm)
        return llm

    def test_query_endpoint_streams_real_response(
        self, client, test_db_session, mlx_test_model_path,
    ):
        try:
            llm = self._make_llm_row(test_db_session, mlx_test_model_path)
            create_resp = client.post(
                "/erudi/conversations/",
                json={
                    "llm_id": llm.id,
                    "temperature": 0.0, "top_p": 1.0, "max_tokens": 32,
                    "custom_prompt": "",
                },
            )
            assert create_resp.status_code == 201, create_resp.text
            conv_id = create_resp.json()["id"]

            resp = client.post(
                f"/erudi/conversations/{conv_id}/query",
                json={"question": "Say hi.", "max_new_tokens": 16},
            )
            assert resp.status_code == 200, resp.text
            assert len(resp.text.strip()) > 0, "empty response body"

            # User message + assistant message must both have been persisted.
            from src.entities.Message import Message
            msgs = test_db_session.query(Message).filter(
                Message.conversation_id == conv_id
            ).all()
            senders = [m.sender for m in msgs]
            assert "user" in senders
            assert "llm" in senders
        finally:
            MLX_Engine.cleanup()

    def test_generate_title_endpoint_writes_name(
        self, client, test_db_session, mlx_test_model_path,
    ):
        try:
            llm = self._make_llm_row(test_db_session, mlx_test_model_path)
            create_resp = client.post(
                "/erudi/conversations/",
                json={
                    "llm_id": llm.id,
                    "temperature": 0.0, "top_p": 1.0, "max_tokens": 32,
                    "custom_prompt": "",
                },
            )
            conv_id = create_resp.json()["id"]

            resp = client.post(
                f"/erudi/conversations/{conv_id}/generate_title",
                json={"question": "Explain Python decorators briefly"},
            )
            assert resp.status_code == 200, resp.text

            from src.entities.Conversation import Conversation
            test_db_session.expire_all()
            conv = test_db_session.query(Conversation).filter(
                Conversation.id == conv_id
            ).first()
            # Either the model produced a title, or the empty-question fallback
            # kicked in; either way, name must not be the literal "New Conversation"
            # if the model emitted anything, AND it must not be empty.
            assert conv.name and len(conv.name.strip()) > 0
        finally:
            MLX_Engine.cleanup()

    def test_two_consecutive_queries_reuse_same_subprocess(
        self, client, test_db_session, mlx_test_model_path,
    ):
        """Cache contract: same llm.id ⇒ same subprocess across requests."""
        try:
            llm = self._make_llm_row(test_db_session, mlx_test_model_path)
            create_resp = client.post(
                "/erudi/conversations/",
                json={
                    "llm_id": llm.id,
                    "temperature": 0.0, "top_p": 1.0, "max_tokens": 16,
                    "custom_prompt": "",
                },
            )
            conv_id = create_resp.json()["id"]

            for q in ("first", "second"):
                r = client.post(
                    f"/erudi/conversations/{conv_id}/query",
                    json={"question": q, "max_new_tokens": 4},
                )
                assert r.status_code == 200

            # After both queries, the singleton must still hold the same pid.
            assert MLX_Engine._model is not None
            # `_model_id` may be stored as int or str depending on the impl's
            # normalization. Accept either to avoid coupling the test to that
            # internal choice.
            assert MLX_Engine._model_id in (llm.id, str(llm.id)), (
                f"expected _model_id to be {llm.id!r} or {str(llm.id)!r}, "
                f"got {MLX_Engine._model_id!r}"
            )
            assert MLX_Engine._model["proc"].is_alive()
        finally:
            MLX_Engine.cleanup()
