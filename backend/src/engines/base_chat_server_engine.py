"""Abstract base for engines that wrap an OpenAI-compatible HTTP server child.

Currently shared by:
- `MLX_Engine`        spawns `mlx_lm.server` via `multiprocessing.Process`
- `BaseLlamaCppEngine` → `CPU_Engine` / `CUDA_Engine`  spawn `llama-server`
  via `subprocess.Popen`

The pattern:

1. Pick a free port in a configurable range.
2. Spawn the child via the abstract `_spawn_child` hook.
3. Two-stage probe: `GET /health` (poll until 200, the upstream `503 loading`
   contract handles model warm-up), then a single `POST /v1/chat/completions`
   with `max_tokens=1` to validate chat template + tokenizer + sampling.
4. Register an `atexit` handler stored on the class so we can unregister it
   before a model switch (fixes the original closure leak — without this,
   every swap would leak a stale handler holding a dead `proc`).
5. Hand back the child's `base_url` + a per-engine `_translate_payload_kwargs`
   hook (mlx_lm.server uses HF/transformers names, llama-server uses its own).
   The agent layer streams tokens over this `base_url` via `ChatOpenAI`; the
   engine no longer parses SSE itself.

The active-marker pattern (`_last_used = None` during a generation, restored
afterwards) lives in `BaseEngine.generation_guard`, which the agent layer
wraps around model resolution + the whole token stream.
"""

from __future__ import annotations

import atexit
import socket
import time
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Optional, Tuple, Union

import requests

from src.core.exceptions import EngineException
from src.core.logging import logger
from src.engines.base_engine import BaseEngine


class BaseChatServerEngine(BaseEngine):
    """Subprocess + OpenAI-compat HTTP + SSE common pattern.

    Subclasses must override the class attributes marked `# must override` and
    implement the four `@abstractmethod` hooks. The rest of the lifecycle (port
    pick, probe, atexit, SSE parsing, idle cleanup) is provided here.
    """

    # ====================== Overridable class attributes ======================
    _port_range_start: ClassVar[int] = 0  # must override
    _port_range_count: ClassVar[int] = 100
    _server_name: ClassVar[str] = ""  # must override — used in error messages
    _server_alias_prefix: ClassVar[str] = "erudi-"
    _tokenizer_provider: ClassVar[str] = ""  # must override
    _probe_timeout_s: ClassVar[float] = 120.0
    _probe_poll_interval_s: ClassVar[float] = 0.4

    # ====================== Per-class state ======================
    # Stored separately from `_model` so we can unregister the atexit handler
    # before swapping models — see `_stop_server_if_running`.
    _atexit_handler: ClassVar[Optional[Callable[[], None]]] = None

    # ====================== Abstract hooks ======================
    @classmethod
    @abstractmethod
    def _spawn_child(cls, *, model_path: Path, alias: str, port: int, **ctx: Any) -> Dict[str, Any]:
        """Spawn the OpenAI-compat child and return the handle dict.

        The handle MUST contain at least: `pid`, `proc`, `port`, `base_url`,
        `alias`, `model_path`. Extra keys (e.g., `threads`, `gpu_layers`) are
        allowed and preserved.

        Implementations may receive subclass-specific context via `**ctx`
        (populated by `_prepare_spawn_context`). For example, CUDA injects
        `gpu_layers` here.
        """

    @classmethod
    @abstractmethod
    def _terminate_process(cls, proc: Any) -> None:
        """Idempotently terminate the child process.

        API differs by spawn type: `mp.Process` for MLX (`terminate`, `kill`,
        `join`); `subprocess.Popen` for llama-cpp engines (`send_signal`,
        `terminate`, `kill`, `wait`). Must accept `None` as a no-op.
        """

    @classmethod
    @abstractmethod
    def _proc_is_alive(cls, proc: Any) -> bool:
        """Whether the spawned child is still alive.

        `mp.Process.is_alive()` vs `subprocess.Popen.poll() is None`. Used by
        `_probe_ready` to catch early subprocess crashes.
        """

    @classmethod
    @abstractmethod
    def _resolve_model_artifact(cls, llm_local_path: Union[str, Path]) -> Path:
        """Resolve the artifact handed to `_spawn_child`.

        MLX returns a directory containing weights + tokenizer; llama-cpp
        engines return a single `.gguf` file (picked by quant-priority
        heuristic in `_select_gguf`).
        """

    @staticmethod
    def _payload_model_value(handle: Dict[str, Any]) -> str:
        """Value to send as the `"model"` field in `/v1/chat/completions`.

        Default: use the handle's `alias` (llama-server convention). MLX
        overrides to return the literal sentinel `"default_model"` (mlx_lm.server
        falls back to the model loaded with `--model` when this sentinel appears).
        """
        return handle["alias"]

    @classmethod
    def _prepare_spawn_context(cls) -> Dict[str, Any]:
        """Build per-spawn context passed to `_spawn_child` as `**ctx`.

        Default: empty. CUDA overrides to inject `{"gpu_layers": ...}` from
        NVML at spawn time.
        """
        return {}

    @classmethod
    def _translate_payload_kwargs(cls, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Translate engine-agnostic kwarg names (HF/transformers vocabulary)
        into the names the upstream server expects.

        Default: identity (mlx_lm.server already uses HF names). LlamaCpp
        engines override to translate `repetition_penalty → repeat_penalty`
        and `repetition_context_size → repeat_last_n`.
        """
        return kwargs

    # ====================== Shared concrete methods ======================
    @classmethod
    def _assert_requests(cls) -> None:
        """Confirm the `requests` library is importable."""
        try:
            import requests  # noqa: F401
        except ImportError as e:
            raise EngineException(
                message=f"`requests` is required to talk to {cls._server_name}",
                trace=str(e),
            )

    @classmethod
    def _assert_required_attrs(cls) -> None:
        """Raise if a subclass forgot to override required class attrs."""
        missing = []
        if cls._port_range_start == 0:
            missing.append("_port_range_start")
        if not cls._server_name:
            missing.append("_server_name")
        if not cls._tokenizer_provider:
            missing.append("_tokenizer_provider")
        if missing:
            raise EngineException(
                message=f"{cls.__name__} did not override required class attrs: {missing}",
            )

    @classmethod
    def _pick_free_port(cls) -> int:
        """Find a free TCP port in `[start, start+count)`.

        TOCTOU caveat: the socket is closed before we hand the port to the
        child, so a racing process could grab it between. `_probe_ready`
        surfaces a hint in the error message when this happens.
        """
        cls._assert_required_attrs()
        for offset in range(cls._port_range_count):
            port = cls._port_range_start + offset
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
        raise EngineException(
            message=(
                f"No free port for {cls._server_name} in range "
                f"{cls._port_range_start}-{cls._port_range_start + cls._port_range_count - 1}"
            ),
        )

    @classmethod
    def _wait_port_closed(cls, port: int, timeout_s: float = 3.0) -> None:
        """Block until the OS releases `port` (TIME_WAIT) or `timeout_s` elapses."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(("127.0.0.1", port))
                return  # port free
            except OSError:
                time.sleep(0.1)
        # If we time out, downstream port pick will skip this port anyway.

    @classmethod
    def _probe_ready(
        cls,
        base_url: str,
        proc: Any = None,
        alias: Optional[str] = None,
    ) -> None:
        """Two-stage readiness probe.

        Stage 1: poll `GET /health` until 200 OK. The upstream contract is:
        - 503 with `{"error": {"message": "Loading model"}}` while the model loads.
        - 200 with `{"status": "ok"}` once ready.
        If `proc` is provided, `_proc_is_alive(proc)` is checked each iteration
        so a child that crashes early (e.g., DLL_NOT_FOUND on Windows) is
        reported immediately rather than timing out at `_probe_timeout_s`.

        Stage 2: send a single `POST /v1/chat/completions` with `max_tokens=1`.
        This validates the chat template + tokenizer + sampling chain — a
        broken GGUF (missing chat template) returns 200 on `/health` but 400
        on the first chat call. The `model` field is built via
        `_payload_model_value({"alias": alias})` when `alias` is provided, so
        each subclass picks the same field name it'd use for real inference
        (llama-cpp returns the alias; MLX returns the `"default_model"`
        sentinel). Without `alias`, falls back to `"default_model"` for
        backward compatibility.
        """
        deadline = time.monotonic() + cls._probe_timeout_s
        last_status: Optional[int] = None
        last_err: Optional[Exception] = None
        while time.monotonic() < deadline:
            if proc is not None and not cls._proc_is_alive(proc):
                raise EngineException(
                    message=(
                        f"{cls._server_name} child exited before becoming ready "
                        f"(early crash). Check backend logs for the child's stderr."
                    ),
                )
            try:
                resp = requests.get(f"{base_url}/health", timeout=2.0)
                last_status = resp.status_code
                if resp.status_code == 200:
                    break
                # 503 (or anything else) → keep polling.
            except requests.RequestException as e:
                last_err = e
            time.sleep(cls._probe_poll_interval_s)
        else:
            port = base_url.rsplit(":", 1)[-1]
            raise EngineException(
                message=(
                    f"{cls._server_name} did not become ready within "
                    f"{cls._probe_timeout_s:.0f}s (last status: {last_status}, "
                    f"last err: {last_err}). If another process bound the port "
                    f"between pick and spawn, the request may be hitting the wrong "
                    f"server — check `lsof -i :{port}`."
                ),
            )
        # Stage 2 — cheap chat-completions ping (1 token).
        if alias is not None:
            model_field = cls._payload_model_value({"alias": alias})
        else:
            # Backward-compat fallback: mlx_lm.server's sentinel, accepted by
            # llama-server as well (it picks the only loaded model).
            model_field = "default_model"
        try:
            resp = requests.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": model_field,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "temperature": 0.0,
                    "stream": False,
                },
                timeout=30.0,
            )
        except requests.RequestException as e:
            raise EngineException(
                message=f"{cls._server_name} chat-completions probe failed",
                trace=str(e),
            )
        if resp.status_code >= 400:
            raise EngineException(
                message=(
                    f"{cls._server_name} chat-completions probe returned "
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                ),
            )

    @classmethod
    def _stop_server_if_running(cls) -> None:
        """Tear down the cached subprocess (if any) and unregister its atexit handler."""
        model = cls._model
        if isinstance(model, dict):
            proc = model.get("proc")
            port = model.get("port")
            if proc is not None:
                logger.info(f"[{cls.__name__}] Stopping {cls._server_name} on port {port}")
                cls._terminate_process(proc)
                if port is not None:
                    cls._wait_port_closed(port)
        # Always clear the atexit handler — even if the proc was already dead,
        # the registered lambda still holds a reference to it.
        if cls._atexit_handler is not None:
            try:
                atexit.unregister(cls._atexit_handler)
            except Exception:
                pass
            cls._atexit_handler = None

    @classmethod
    def cleanup(cls) -> None:
        """Terminate the child and reset cached engine state.

        Called by `BaseEngine._cleanup_monitor` after 300s of idle, or
        explicitly when switching models.
        """
        with cls._lock:
            cls._stop_server_if_running()
            return super().cleanup()

    # ====================== Template methods ======================
    @classmethod
    def _start_server(cls, *, model_path: Path, alias: str, port: int) -> Dict[str, Any]:
        """Spawn the child, probe, and register a stable atexit handler.

        The atexit handler is stored on `cls._atexit_handler` so a subsequent
        `_stop_server_if_running` (during a model swap) can unregister it.
        """
        cls._assert_required_attrs()
        cls._assert_requests()
        ctx = cls._prepare_spawn_context()
        handle = cls._spawn_child(model_path=model_path, alias=alias, port=port, **ctx)
        try:
            cls._probe_ready(
                handle["base_url"],
                proc=handle.get("proc"),
                alias=handle.get("alias"),
            )
        except Exception:
            cls._terminate_process(handle.get("proc"))
            raise
        proc = handle.get("proc")

        def _atexit_handler() -> None:
            cls._terminate_process(proc)

        atexit.register(_atexit_handler)
        cls._atexit_handler = _atexit_handler
        return handle

    @classmethod
    def get_model_and_tokenizer(
        cls,
        llm_id: str,
        llm_local_path: Union[str, Path],
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Spawn (or reuse) the child server for `llm_id`.

        Singleton semantics: a second call with the same `llm_id` reuses the
        existing subprocess; a call with a different `llm_id` terminates the
        old child (including unregistering its atexit handler) before spawning.
        """
        logger.info(
            f"[{cls.__name__}] Loading model '{llm_id}' from {llm_local_path} "
            f"via {cls._server_name}..."
        )
        with cls._lock:
            if cls._should_not_reload_model(llm_id):
                return cls._return_cached_model_and_tokenizer()
            cls._assert_requests()
            resolved = cls._resolve_model_artifact(llm_local_path)
            # Stop previous child (also unregisters its stale atexit handler).
            cls._stop_server_if_running()
            alias = f"{cls._server_alias_prefix}{llm_id}"
            port = cls._pick_free_port()
            handle = cls._start_server(model_path=resolved, alias=alias, port=port)
            cls._model = handle
            cls._tokenizer = {"type": "remote", "provider": cls._tokenizer_provider}
            cls._model_id = llm_id
            cls._last_used = datetime.now()
            logger.info(
                f"[{cls.__name__}] Model loaded on {handle['base_url']} alias={alias}"
            )
            return cls._model, cls._tokenizer
