"""Abstract sub-base for engines that wrap the `llama-server` binary.

Sits between `BaseChatServerEngine` and the concrete `CPU_Engine` /
`CUDA_Engine` classes. Factors the bits CPU and CUDA share but MLX does
not:

- Where the binary lives (`backend/artifacts/llama-cpp/<cpu|cuda>/bin/llama-server`)
- How to find / pick the GGUF file in a model directory
- The `subprocess.Popen` lifecycle (terminate, alive check)
- Kwarg-name translation from Erudi's vocabulary (HF/transformers) to the
  llama.cpp wire names (`repetition_penalty` → `repeat_penalty`,
  `repetition_context_size` → `repeat_last_n`).

Subclasses choose:
- `_use_cuda_build` (False for CPU, True for CUDA — selects artifact dir)
- `_build_spawn_argv` (CPU forces `-ngl 0`; CUDA injects computed `-ngl`)
- `_build_spawn_env` (CUDA prepends the CUDA toolkit to `PATH`)
- `_tokenizer_provider` (just for the placeholder dict)
"""

from __future__ import annotations

import os
import platform
import signal
import subprocess
from abc import abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Union

from src.core.config import ROOT_DIR
from src.core.exceptions import EngineException
from src.core.logging import logger
from src.engines.base_chat_server_engine import BaseChatServerEngine


class BaseLlamaCppEngine(BaseChatServerEngine):
    """Shared scaffolding for engines that spawn `llama-server` via Popen."""

    # ====================== Overridable class attrs ======================
    # llama-server uses the 8080+ range historically (collision-free against
    # MLX which uses 9080+ and the Erudi backend which uses 8765-8799).
    _port_range_start: ClassVar[int] = 8080

    # Subclass selects which artifact directory to look in.
    # False → `artifacts/llama-cpp/cpu/bin`, True → `artifacts/llama-cpp/cuda/bin`.
    _use_cuda_build: ClassVar[bool] = False

    # Every llama-cpp engine (CPU + CUDA) consumes pre-built **public** GGUF repos.
    # The catalog is built by searching filter="gguf" (any author) and resolving each
    # base id to its public GGUF repo — no hand-maintained mapping, token-free by
    # construction (the gated first-party safetensors is never a GGUF, so never seen).
    USES_GGUF: ClassVar[bool] = True
    FORMAT_TAG = "gguf"

    # ====================== Concrete shared methods ======================
    @classmethod
    def _default_install_dir(cls) -> Path:
        """Resolve the directory that holds `llama-server` for this engine."""
        flavour = "cuda" if cls._use_cuda_build else "cpu"
        return ROOT_DIR / "artifacts" / "llama-cpp" / flavour / "bin"

    @classmethod
    def _find_llama_server(cls, install_dir: Optional[Path] = None) -> Path:
        """Return the absolute path of the `llama-server` binary, or raise.

        Tries the configured flavour first, then falls back to the other
        flavour (a CUDA-built artifact runs CPU inference fine; the CPU
        artifact would just refuse to use the GPU). This preserves the
        existing fallback behaviour from cpu_engine.py.
        """
        install = install_dir or cls._default_install_dir()
        exe = "llama-server.exe" if os.name == "nt" else "llama-server"
        primary = install / exe
        if primary.exists():
            return primary
        # Fallback to the other flavour.
        other = "cpu" if cls._use_cuda_build else "cuda"
        fallback = ROOT_DIR / "artifacts" / "llama-cpp" / other / "bin" / exe
        if fallback.exists():
            return fallback
        raise EngineException(
            message=(
                f"llama-server binary not found at {primary} or {fallback}. "
                f"Build llama.cpp first (see scripts/dev/backend/build-llamacpp-*)."
            ),
        )

    @classmethod
    def _select_gguf(cls, llm_local_path: Union[str, Path]) -> Path:
        """Pick the best GGUF file from `llm_local_path` (file or directory).

        Priority when a directory contains multiple GGUFs:
        `q4_k_m > q4_0 > q5_k_m > q8_0 > f16`, then smallest file.
        """
        p = Path(llm_local_path).resolve()
        if not p.exists():
            raise EngineException(message=f"Model path not found: {p}")
        if p.is_file():
            if p.suffix.lower() != ".gguf":
                raise EngineException(
                    message=f"Expected a .gguf file. Got: {p}",
                )
            return p
        ggufs = [g for g in p.glob("*.gguf") if "mmproj" not in g.name.lower()]
        if not ggufs:
            raise EngineException(
                message=f"No .gguf found in {p}. Convert or quantize first.",
            )
        if len(ggufs) == 1:
            return ggufs[0]
        QUANT_PRIORITY = ["q4_k_m", "q4_0", "q5_k_m", "q8_0", "f16"]
        for quant in QUANT_PRIORITY:
            for gguf in ggufs:
                if quant in gguf.stem.lower():
                    logger.info(
                        f"[{cls.__name__}] Selected {gguf.name} (quant: {quant})"
                    )
                    return gguf
        smallest = min(ggufs, key=lambda x: x.stat().st_size)
        logger.warning(
            f"[{cls.__name__}] No known quant pattern; using smallest: {smallest.name}"
        )
        return smallest

    @classmethod
    def _find_mmproj(cls, model_gguf: Path) -> Optional[Path]:
        """Return the mmproj GGUF in the same directory as model_gguf, or None."""
        candidates = list(model_gguf.parent.glob("mmproj-*.gguf"))
        if not candidates:
            return None
        if len(candidates) > 1:
            logger.warning(f"[{cls.__name__}] Multiple mmproj files found, using {candidates[0].name}")
        return candidates[0]

    @classmethod
    def _resolve_model_artifact(cls, llm_local_path: Union[str, Path]) -> Path:
        """For llama-cpp engines the artifact is a single GGUF file."""
        return cls._select_gguf(llm_local_path)

    @classmethod
    def _load_capability_tokenizer(cls, llm_local_path: Union[str, Path]):
        """Load the tokenizer embedded in the GGUF (metadata only, no weights).

        Used by ``compute_supports_tools`` for static tool-calling detection.
        ``transformers`` reads the GGUF chat template via the ``gguf`` package.
        """
        from transformers import AutoTokenizer

        gguf_path = cls._select_gguf(llm_local_path)
        return AutoTokenizer.from_pretrained(
            str(gguf_path.parent), gguf_file=gguf_path.name, trust_remote_code=False
        )

    @classmethod
    def model_supports_vision(cls, llm_local_path: Union[str, Path]) -> Optional[bool]:
        """A llama.cpp model is vision-capable iff it ships an ``mmproj`` projector.

        That is exactly the file the engine passes to ``llama-server --mmproj``
        (#130). No artifact / unreadable directory -> ``None`` (permissive).
        """
        try:
            gguf_path = cls._select_gguf(llm_local_path)
            return cls._find_mmproj(gguf_path) is not None
        except Exception:
            logger.warning(
                f"[{cls.__name__}] vision detection failed for {llm_local_path}"
            )
            return None

    @classmethod
    def _terminate_process(cls, proc: Any) -> None:
        """Idempotent terminate for `subprocess.Popen`.

        macOS/Linux: SIGINT → wait 5s → SIGKILL.
        Windows: terminate → wait 5s → kill.
        """
        if not proc:
            return
        try:
            if proc.poll() is None:
                if platform.system() == "Windows":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
        except Exception:
            pass  # best-effort

    @classmethod
    def _proc_is_alive(cls, proc: Any) -> bool:
        """Whether the Popen child is still running."""
        if proc is None:
            return False
        try:
            return proc.poll() is None
        except Exception:
            return False

    @classmethod
    def _translate_payload_kwargs(cls, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Translate from Erudi vocabulary (HF/transformers) to llama-server names."""
        renames = {
            "repetition_penalty": "repeat_penalty",
            "repetition_context_size": "repeat_last_n",
        }
        return {renames.get(k, k): v for k, v in kwargs.items()}

    @classmethod
    def _spawn_child(
        cls,
        *,
        model_path: Path,
        alias: str,
        port: int,
        **ctx: Any,
    ) -> Dict[str, Any]:
        """Spawn `llama-server` via Popen. Subclasses inject CLI/env via hooks.

        Hooks called by this method:
        - `_build_spawn_argv(*, llama_server, model_gguf, alias, port, **ctx)`
        - `_build_spawn_env()`
        """
        install_dir = cls._default_install_dir()
        llama_server = cls._find_llama_server(install_dir)
        argv = cls._build_spawn_argv(
            llama_server=llama_server,
            model_gguf=model_path,
            alias=alias,
            port=port,
            **ctx,
        )
        mmproj = cls._find_mmproj(model_path)
        if mmproj:
            argv += ["--mmproj", str(mmproj)]
            logger.info(f"[{cls.__name__}] Vision projector found: {mmproj.name}")
        env = cls._build_spawn_env()
        proc = subprocess.Popen(
            [str(a) for a in argv],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env,
        )
        handle: Dict[str, Any] = {
            "pid": proc.pid,
            "proc": proc,
            "port": port,
            "base_url": f"http://127.0.0.1:{port}",
            "alias": alias,
            "model_path": str(model_path),
        }
        # Preserve subclass-relevant context items in the handle so observability
        # (logs, debug endpoints) shows e.g. how many threads / GPU layers were used.
        for k in ("threads", "gpu_layers", "ctx_size"):
            if k in ctx:
                handle[k] = ctx[k]
        return handle

    # ====================== Abstract subclass hooks ======================
    @classmethod
    @abstractmethod
    def _build_spawn_argv(
        cls,
        *,
        llama_server: Path,
        model_gguf: Path,
        alias: str,
        port: int,
        **ctx: Any,
    ) -> List[Any]:
        """Build the CLI for `llama-server`. CPU forces `-ngl 0`, CUDA injects
        `-ngl <gpu_layers>` from `_prepare_spawn_context`."""

    @classmethod
    def _build_spawn_env(cls) -> Dict[str, str]:
        """Per-spawn environment. Default: inherit the parent env unchanged.
        CUDA overrides to prepend the CUDA toolkit bin to `PATH` so the
        runtime DLLs resolve.
        """
        return os.environ.copy()

    # Note: `_copy_auxiliary_files` and `quant_and_save_from_hf_format` stay
    # in concrete subclasses for now. The conversion / quantization pipeline
    # is much heavier than the runtime path and will be factored in a
    # follow-up PR if duplication justifies it.
