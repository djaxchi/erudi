"""MLX engine for Apple Silicon inference via `mlx_vlm.server` subprocess.

Inference is delegated to an out-of-process `mlx_vlm.server` HTTP server
(OpenAI-compatible), spawned by `multiprocessing.Process` and reached over
loopback HTTP — exactly aligned with the CPU/CUDA pattern that wraps the
`llama-server` binary. mlx-vlm is a superset of mlx-lm (it depends on it): it
serves plain text models, carries a working tool-calling parser (no
mlx_lm.server EOS-flush drop, so agentic tools fire), and accepts image input.
Quantization helpers (`quant_and_save_from_hf_format`) and Apple Silicon
hardware detection remain in-process: they don't need the server and would
only inflate cold-start time if they did.

Architecture:
    MLX_Engine (singleton)
    ┌───────────────────────────────────────────────────────────────┐
    │ get_model_and_tokenizer(llm_id, path)                         │
    │  1. Pick free TCP port (9080+)                                │
    │  2. Spawn child: mp.Process(target=run_mlx_vlm_server)        │
    │  3. Poll GET /health until 200 (≤120s)                        │
    │  4. atexit.register(terminate)                                │
    │  5. Cache handle {pid,proc,port,base_url,alias,model_path}    │
    └───────────────────────────────────────────────────────────────┘
                                  ↓
    ┌───────────────────────────────────────────────────────────────┐
    │ token streaming lives in the agent layer, not the engine:     │
    │   AgentRunner → ChatOpenAI(base_url) → POST /v1/chat/...      │
    │   ChatOpenAI yields delta.content, ignores delta.reasoning    │
    └───────────────────────────────────────────────────────────────┘
                                  ↓
    ┌───────────────────────────────────────────────────────────────┐
    │ cleanup() — override                                          │
    │  └─> SIGTERM child → join(5s) → SIGKILL if needed             │
    │      → wait_port_closed → super().cleanup()                   │
    └───────────────────────────────────────────────────────────────┘

Why multiprocessing instead of subprocess.Popen([sys.executable, "-m", ...])?
    In a PyInstaller frozen build, `sys.executable` is the launcher binary,
    not a Python interpreter, so the `-m` flag is a no-op. `mp.spawn`
    (already configured in `backend/run.py:143-160` via `mp.freeze_support()`
    + `set_start_method("spawn", force=True)`) re-executes the binary in
    child mode and reconstitutes the import graph — the same `run_mlx_vlm_server`
    target works in dev (real Python) and in prod (frozen).

Why the `<|channel>thought ... <channel|>` manual filter is gone:
    `mlx_vlm.server` surfaces reasoning text in a dedicated
    `choices[0].delta.reasoning` field (like mlx_lm.server did) — the agent
    layer (ChatOpenAI) simply ignores it, matching the previous in-engine filter.

Why the `_MLX_EXECUTOR` thread bottleneck is gone:
    Generation now runs in a separate OS process; the GPU stream is
    initialised inside that child, fully isolated from the FastAPI parent.
    The Stream(gpu, 0) crash that motivated the persistent thread executor
    (commits cefdc7a, 40fb55e) is structurally impossible from the parent.

Quantization Mapping:
    Maps HuggingFace model IDs to MLX-quantized 4-bit variants:
    - mistralai/Mistral-7B-Instruct-v0.3 → mlx-community/.../4bit
    - google/gemma-2-2b-it → mlx-community/.../4bit
    Used by the downloader to fetch the right mlx-community/* repo;
    `quant_and_save_from_hf_format` handles HF-SafeTensors → MLX 4-bit
    conversion via `mlx_vlm.convert()` (in-process — no subprocess).

Example:
    ::

        from src.engines.mlx_engine import MLX_Engine

        model, tokenizer = MLX_Engine.get_model_and_tokenizer(
            llm_id="mistral-7b",
            llm_local_path="/path/to/mlx/model"
        )
        # Token streaming is driven by the agent layer (ChatOpenAI(base_url=...)),
        # not the engine; ``model["base_url"]`` is what it connects to.
        MLX_Engine.cleanup()

Warning:
    Only use on Apple Silicon. On other platforms, BaseEngine.get_engine()
    will select CUDA_Engine or CPU_Engine instead.
"""

from __future__ import annotations

import importlib  # used by quant_and_save_from_hf_format
import logging
import multiprocessing as mp
import os
import platform
import shutil
import subprocess
import time  # used by hardware warm-up loop
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.engines.base_chat_server_engine import BaseChatServerEngine
from src.engines._mlx_vlm_server_runner import run_mlx_vlm_server
from src.core.exceptions import (
    FileSystemException,
    HardwareException,
    InsufficientMemoryException,
    QuantizationException,
)


class MLX_Engine(BaseChatServerEngine):
    """Singleton Engine for MLX models and tokenizers runtimes.
    Built for Apple Silicon Backends.
    """
    # Mapping of original model links to MLX-quantized versions (same as in llm_downloader.py)
    MODEL_MAPPING : dict = {
        "google/gemma-3-270m-it":              "mlx-community/gemma-3-270m-it-4bit",
        "google/gemma-3-1b-it":                "mlx-community/gemma-3-1b-it-4bit",
        "google/gemma-3-4b-it":                "mlx-community/gemma-3-4b-it-4bit",
        "google/gemma-3-12b-it":               "mlx-community/gemma-3-12b-it-4bit",
        "google/gemma-2-2b-it":                "mlx-community/gemma-2-2b-it-4bit",
        "google/gemma-4-E2B-it":               "mlx-community/gemma-4-e2b-it-4bit",
        "google/gemma-4-E4B-it":               "mlx-community/gemma-4-e4b-it-4bit",
        "mistralai/Mistral-7B-Instruct-v0.3":  "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
        "mistralai/Mistral-7B-v0.3":           "mlx-community/Mistral-7B-v0.3-4bit",
        "mistralai/Ministral-8B-Instruct-2410": "mlx-community/Ministral-8B-Instruct-2410-4bit",
        "mistralai/Mistral-Nemo-Instruct-2407": "mlx-community/Mistral-Nemo-Instruct-2407-4bit",
        "meta-llama/Llama-3.2-3B-Instruct":    "mlx-community/Llama-3.2-3B-Instruct-4bit",
        "meta-llama/Llama-3.1-8B-Instruct":    "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        "meta-llama/Llama-3-8B-Instruct":      "mlx-community/Meta-Llama-3-8B-Instruct-4bit",
        "Qwen/Qwen2.5-7B-Instruct":            "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "Qwen/Qwen2.5-VL-3B-Instruct":         "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
        "google/gemma-4-26b-a4b-it":           "mlx-community/gemma-4-26b-a4b-it-4bit",
        "google/gemma-4-31b-it":               "mlx-community/gemma-4-31b-it-4bit",
    }

    @classmethod
    def quant_and_save_from_hf_format(
        cls,
        local_hf_path: Union[str, Path],
        local_dest_path: Union[str, Path],
        quantize: bool = True,
        q_bits: int = 4,
    ) -> None:
        """Convert HuggingFace model to MLX 4-bit quantized format.

        Args:
            local_hf_path: Path to HuggingFace model directory (SafeTensors format).
            local_dest_path: Destination path for quantized MLX model.
            quantize: Whether to apply quantization. Defaults to True.
            q_bits: Quantization bits ("4" for 4-bit). Defaults to "4".

        Returns:
            None. Quantized model saved to local_dest_path.

        Raises:
            Exception: If mlx_vlm.convert() fails (corrupted weights, OOM, etc.).

        Note:
            Uses mlx_vlm.convert() (same kwargs as mlx_lm.convert) which removes
            the existing destination directory. mlx-vlm's converter preserves
            vision/audio projections, so it quantizes both text and VL models;
            4-bit quantization reduces model size by ~75% with minimal quality loss.
        """
        mlx_vlm = importlib.import_module("mlx_vlm")
        local_hf_path = str(local_hf_path)
        local_dest_path = str(local_dest_path)

        try:
            logging.info("Starting conversion from HF to MLX")
            start = datetime.now()
            if os.path.exists(local_dest_path):
                shutil.rmtree(local_dest_path, ignore_errors=True)
            mlx_vlm.convert(
                local_hf_path,
                mlx_path=local_dest_path,
                quantize=quantize,
                q_bits=q_bits
            )
            logging.info(f"Model converted to mlx in {datetime.now() - start}")
        except FileNotFoundError as e:
            raise FileSystemException(
                f"HF model not found at {local_hf_path}",
                trace=str(e)
            )
        except OSError as e:
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise FileSystemException(
                    f"Disk space issue during quantization: {e}",
                    trace=str(e)
                )
            raise FileSystemException(
                f"Filesystem error during quantization: {e}",
                trace=str(e)
            )
        except MemoryError as e:
            raise InsufficientMemoryException(
                "model quantization",
                trace=str(e)
            )
        except Exception as e:
            raise QuantizationException(
                f"MLX quantization failed: {e}",
                trace=str(e)
            )

    # ======================= SUBPROCESS HTTP SERVER (mlx_vlm.server) =======================
    #
    # Inference goes through a subprocess `mlx_vlm.server` (OpenAI-compatible HTTP),
    # spawned via `multiprocessing.Process(target=run_mlx_vlm_server, args=([argv],))`.
    # mlx-vlm is a superset of mlx-lm: it serves plain text models through the same
    # endpoint, carries its own tool-calling parser (no mlx_lm.server EOS-flush drop,
    # so agentic tool use works on Apple Silicon), and accepts image input. The
    # shared lifecycle (port pick, /health + chat-ping probe, SSE parsing, atexit,
    # idle cleanup) lives in `BaseChatServerEngine`. Only the hooks below are
    # MLX-specific.
    #
    # Why `multiprocessing` and not `subprocess.Popen([sys.executable, "-m", ...])`:
    # in a PyInstaller frozen build, `sys.executable` is the launcher binary, not
    # a Python interpreter. `mp.spawn` (configured in `backend/run.py`) re-executes
    # the binary in child mode and reconstitutes the import graph, so the same
    # `run_mlx_vlm_server` target works in dev (real Python) and in prod (frozen).

    # --- BaseChatServerEngine config overrides ---
    _port_range_start = 9080
    _server_name = "mlx_vlm.server"
    _tokenizer_provider = "mlx-vlm-server"
    # mlx_vlm.server accepts HF/transformers kwarg names natively (repetition_penalty,
    # repetition_context_size, top_k, ...), so MLX keeps the identity
    # `_translate_payload_kwargs`; model_factory sends them via ChatOpenAI extra_body.

    @staticmethod
    def _payload_model_value(handle: Dict[str, Any]) -> str:
        """mlx_vlm.server resolves every request's `model` field through
        `get_cached_model(request.model)` (there is no `default_model`
        sentinel), so the chat payload must carry the real model path that was
        preloaded with `--model`. The same value is used by the chat-ping probe
        and by ChatOpenAI for real inference (model_factory)."""
        return handle["model_path"]

    @classmethod
    def _resolve_model_artifact(cls, llm_local_path: Union[str, Path]) -> Path:
        """MLX models are directories containing weights + tokenizer."""
        path = Path(llm_local_path).resolve()
        if not path.exists():
            raise FileSystemException(f"MLX model path not found: {path}")
        return path

    @classmethod
    def _spawn_child(
        cls,
        *,
        model_path: Path,
        alias: str,
        port: int,
        **ctx: Any,
    ) -> Dict[str, Any]:
        """Spawn `mlx_vlm.server` as an mp.Process. Returns the handle dict."""
        argv = [
            "mlx_vlm.server",
            "--model", str(model_path),
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "INFO",
        ]
        proc = mp.Process(target=run_mlx_vlm_server, args=(argv,), daemon=False)
        proc.start()
        return {
            "pid": proc.pid,
            "proc": proc,
            "port": port,
            "base_url": f"http://127.0.0.1:{port}",
            "alias": alias,
            "model_path": str(model_path),
        }

    @classmethod
    def _terminate_process(cls, proc) -> None:
        """Idempotently terminate an `mp.Process`, escalating to SIGKILL if needed.

        Accepts `None` (no-op) and `MagicMock`-like proxies for testability.
        Mirrors the bounded-time semantics of cpu_engine.py:226-240, but uses
        `mp.Process` API (`terminate` = SIGTERM, `kill` = SIGKILL).
        """
        if not proc:
            return
        try:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=2)
        except Exception:
            # Best-effort cleanup; never let teardown errors mask the real
            # failure that triggered termination in the first place.
            pass

    @classmethod
    def _proc_is_alive(cls, proc: Any) -> bool:
        """Whether the spawned `mp.Process` is still running.

        Used by `BaseChatServerEngine._probe_ready` to detect early child
        crashes (otherwise the probe would time out at 120s with no hint
        about why the child went away).
        """
        if proc is None:
            return False
        try:
            return bool(proc.is_alive())
        except Exception:
            return False

    # ======================= HARDWARE DETECTION & EVALUATION =======================
    
    # Apple Silicon specifications database (official Apple specs)
    _APPLE_SILICON_SPECS = {
        "M1": {
            "gpu_cores": 8,
            "memory_bandwidth": 68.25,
            "neural_engine_tops": 11.0,
            "cpu_cores": {"performance": 4, "efficiency": 4},
            "max_memory": 16,
            "architecture": "5nm",
        },
        "M1 Pro": {
            "gpu_cores": 16,
            "memory_bandwidth": 200,
            "neural_engine_tops": 11.0,
            "cpu_cores": {"performance": 8, "efficiency": 2},
            "max_memory": 32,
            "architecture": "5nm",
        },
        "M1 Max": {
            "gpu_cores": 32,
            "memory_bandwidth": 400,
            "neural_engine_tops": 11.0,
            "cpu_cores": {"performance": 8, "efficiency": 2},
            "max_memory": 64,
            "architecture": "5nm",
        },
        "M1 Ultra": {
            "gpu_cores": 64,
            "memory_bandwidth": 800,
            "neural_engine_tops": 22.0,
            "cpu_cores": {"performance": 16, "efficiency": 4},
            "max_memory": 128,
            "architecture": "5nm",
        },
        "M2": {
            "gpu_cores": 10,
            "memory_bandwidth": 100,
            "neural_engine_tops": 15.8,
            "cpu_cores": {"performance": 4, "efficiency": 4},
            "max_memory": 24,
            "architecture": "5nm",
        },
        "M2 Pro": {
            "gpu_cores": 19,
            "memory_bandwidth": 200,
            "neural_engine_tops": 15.8,
            "cpu_cores": {"performance": 8, "efficiency": 4},
            "max_memory": 32,
            "architecture": "5nm",
        },
        "M2 Max": {
            "gpu_cores": 38,
            "memory_bandwidth": 400,
            "neural_engine_tops": 15.8,
            "cpu_cores": {"performance": 8, "efficiency": 4},
            "max_memory": 96,
            "architecture": "5nm",
        },
        "M2 Ultra": {
            "gpu_cores": 76,
            "memory_bandwidth": 800,
            "neural_engine_tops": 31.6,
            "cpu_cores": {"performance": 16, "efficiency": 8},
            "max_memory": 192,
            "architecture": "5nm",
        },
        "M3": {
            "gpu_cores": 10,
            "memory_bandwidth": 100,
            "neural_engine_tops": 18.0,
            "cpu_cores": {"performance": 4, "efficiency": 4},
            "max_memory": 24,
            "architecture": "3nm",
        },
        "M3 Pro": {
            "gpu_cores": 18,
            "memory_bandwidth": 150,
            "neural_engine_tops": 18.0,
            "cpu_cores": {"performance": 6, "efficiency": 6},
            "max_memory": 36,
            "architecture": "3nm",
        },
        "M3 Max": {
            "gpu_cores": 40,
            "memory_bandwidth": 400,
            "neural_engine_tops": 18.0,
            "cpu_cores": {"performance": 8, "efficiency": 4},
            "max_memory": 128,
            "architecture": "3nm",
        },
        "M4": {
            "gpu_cores": 10,
            "memory_bandwidth": 120,
            "neural_engine_tops": 38.0,
            "cpu_cores": {"performance": 4, "efficiency": 6},
            "max_memory": 32,
            "architecture": "3nm",
        },
        "M4 Pro": {
            "gpu_cores": 20,
            "memory_bandwidth": 273,
            "neural_engine_tops": 38.0,
            "cpu_cores": {"performance": 10, "efficiency": 4},
            "max_memory": 64,
            "architecture": "3nm",
        },
        "M4 Max": {
            "gpu_cores": 40,
            "memory_bandwidth": 546,
            "neural_engine_tops": 38.0,
            "cpu_cores": {"performance": 12, "efficiency": 4},
            "max_memory": 128,
            "architecture": "3nm",
        },
    }

    @classmethod
    def _detect_apple_silicon_chip(cls) -> Optional[str]:
        """Detect specific Apple Silicon chip model (M1, M2, M3, M4, etc.).
        
        Uses system_profiler command to identify the exact chip variant.
        
        Returns:
            Optional[str]: Chip model (e.g., "M3 Max") or None if not detected.
            
        Note:
            Internal method. Called by get_hardware_info().
        """
        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                hardware_data = data.get("SPHardwareDataType", [{}])[0]
                chip_name = hardware_data.get("chip_type", "")
                
                if chip_name:
                    for model_key in cls._APPLE_SILICON_SPECS.keys():
                        if model_key.replace(" ", "").lower() in chip_name.replace(" ", "").lower():
                            return model_key
            
            return None
            
        except Exception as e:
            logging.warning(f"Failed to detect Apple Silicon chip: {e}")
            return None

    @classmethod
    def _mps_available(cls) -> bool:
        """Check if Metal Performance Shaders (MPS) is available.
        
        Returns:
            bool: True if MPS backend is available in PyTorch.
        """
        # Import required modules for hardware detection
        try:
            import torch
        except ImportError as e:
            logging.warning(f"Optional hardware detection dependency missing: {e}")

        try:
            return torch.backends.mps.is_available()
        except Exception:
            return False

    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        """Get comprehensive hardware information for Apple Silicon.
        
        Returns detailed hardware specifications including Apple chip model,
        unified memory, MPS availability, and Neural Engine specs.
        
        Returns:
            Dict containing hardware specifications following BaseEngine contract:
            {
                "system": {"platform": "Darwin", ...},
                "cpu": {"model": str, "is_apple_silicon": True, ...},
                "memory": {"total_memory_gb": float, "memory_type": "unified", ...},
                "gpu": {"gpu_name": str, "mlx_gpu_cores": int, "unified_memory": True, ...},
                "accelerator": {"neural_engine_tops": float, "architecture": str},
                "storage": {"total_gb": float, "available_gb": float},
                "backend_type": "mlx",
                "timestamp": float
            }
            
        Raises:
            HardwareException: If critical hardware detection fails.
            
        Note:
            Returns fallback values on non-critical failures rather than raising.
            
        Examples:
            >>> hw_info = MLX_Engine.get_hardware_info()
            >>> print(f"Chip: {hw_info['cpu']['model']}")
            >>> print(f"GPU Cores: {hw_info['gpu']['mlx_gpu_cores']}")
        """
        try:
            
            # Import required modules for hardware detection
            try:
                import psutil
                import cpuinfo
            except ImportError as e:
                logging.warning(f"Optional hardware detection dependency missing: {e}")

            # Detect chip model
            chip_model = cls._detect_apple_silicon_chip()
            
            # Get unified memory info
            vm = psutil.virtual_memory()
            total_memory_gb = vm.total / (1024**3)
            available_memory_gb = vm.available / (1024**3)
            memory_pressure = 1.0 - (vm.available / vm.total)
            
            # Get storage info
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            disk_total_gb = disk.total / (1024**3)
            disk_available_gb = disk.free / (1024**3)
            disk_usage_pct = disk.percent
            
            # Get CPU info
            cpu_info_data = cpuinfo.get_cpu_info()
            cpu_model = cpu_info_data.get("brand_raw", "Apple Silicon CPU")
            total_cores = psutil.cpu_count(logical=False)
            logical_cores = psutil.cpu_count(logical=True)
            
            # Get chip specifications
            specs = cls._APPLE_SILICON_SPECS.get(chip_model, {}) if chip_model else {}
            gpu_cores = specs.get("gpu_cores", 0)
            memory_bandwidth = specs.get("memory_bandwidth", 0.0)
            neural_engine_tops = specs.get("neural_engine_tops", 0.0)
            architecture = specs.get("architecture", "Unknown")
            max_memory = specs.get("max_memory", 0)
            cpu_cores_breakdown = specs.get("cpu_cores", {})
            
            # Estimate TFLOPS (Apple doesn't publish official values)
            estimated_tflops = gpu_cores * 0.35 if gpu_cores else 0.0
            
            # Check MPS availability
            mps_supported = cls._mps_available()
            
            # Build hardware info dictionary
            hardware_info = {
                "system": {
                    "platform": platform.system(),
                    "platform_version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor()
                },
                "cpu": {
                    "model": cpu_model,
                    "architecture": platform.machine(),
                    "total_cores": total_cores,
                    "logical_cores": logical_cores,
                    "is_apple_silicon": True,
                    "performance_cores": cpu_cores_breakdown.get("performance"),
                    "efficiency_cores": cpu_cores_breakdown.get("efficiency"),
                },
                "memory": {
                    "total_memory_gb": round(total_memory_gb, 2),
                    "available_memory_gb": round(available_memory_gb, 2),
                    "memory_pressure": round(memory_pressure, 3),
                    "memory_type": "unified"
                },
                "gpu": {
                    "gpu_name": f"Apple {chip_model} GPU" if chip_model else "Apple GPU",
                    "mlx_gpu_cores": gpu_cores,
                    "memory_bandwidth_gbs": memory_bandwidth,
                    "mps_supported": mps_supported,
                    "unified_memory": True,
                    "estimated_tflops": round(estimated_tflops, 2),
                },
                "accelerator": {
                    "neural_engine_tops": neural_engine_tops,
                    "architecture": architecture,
                },
                "storage": {
                    "total_gb": round(disk_total_gb, 2),
                    "available_gb": round(disk_available_gb, 2),
                    "usage_percentage": round(disk_usage_pct, 2)
                },
                "backend_type": "mlx",
                "mlx_chip_model": chip_model,
                "timestamp": time.time()
            }
            
            logging.info(f"MLX hardware detected: {chip_model}, {gpu_cores} GPU cores, {total_memory_gb:.1f}GB unified memory")
            return hardware_info
            
        except Exception as e:
            logging.exception(f"MLX hardware detection failed: {e}")
            raise HardwareException(
                "Failed to detect Apple Silicon hardware",
                trace=str(e)
            )

    @classmethod
    def warm_up_accelerator(cls, duration_seconds: float = 1.0) -> bool:
        """Warm up Apple Silicon GPU using Metal Performance Shaders.
        
        Runs matrix operations on MPS device to bring GPU to optimal performance
        state before benchmarking or inference.
        
        Args:
            duration_seconds: How long to run warm-up operations (default: 1.0).
            
        Returns:
            bool: True if warm-up completed successfully, False otherwise.
            
        Note:
            Particularly important for Apple Silicon due to dynamic clock management.
            
        Examples:
            >>> success = MLX_Engine.warm_up_accelerator(1.5)
            >>> if success:
            ...     print("MPS device ready")
        """
        if not cls._mps_available():
            logging.warning("MPS not available, skipping GPU warm-up")
            return False
        
        try:
            
            # Import required modules for hardware detection
            try:
                import torch
            except ImportError as e:
                logging.warning(f"Optional hardware detection dependency missing: {e}")
                

            logging.info(f"Warming up MPS device for {duration_seconds}s...")
            start_time = time.time()
            
            # Create tensors on MPS device
            device = torch.device("mps")
            size = 4096
            
            while (time.time() - start_time) < duration_seconds:
                # Matrix multiplication on GPU
                a = torch.randn(size, size, device=device)
                b = torch.randn(size, size, device=device)
                c = torch.matmul(a, b)
                
                # Small sleep to prevent CPU overload
                time.sleep(0.05)
            
            logging.info("MPS warm-up completed successfully")
            return True
            
        except Exception as e:
            logging.exception(f"MPS warm-up failed: {e}")
            return False

    @classmethod
    def get_performance_evaluation(cls) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics for Apple Silicon.
        
        Evaluates hardware capabilities and returns performance scores for
        inference and fine-tuning workloads. Scoring optimized for Apple
        Silicon unified memory architecture.
        
        Scoring methodology:
            - Inference: GPU compute (35%), memory bandwidth (30%), memory (20%),
              Neural Engine (10%), CPU (5%)
            - Fine-tuning: Memory capacity (40%), GPU compute (25%),
              memory bandwidth (20%), Neural Engine (10%), CPU (5%)
        
        Returns:
            Dict containing performance metrics and scores (0-100 scale):
            {
                "backend_type": "mlx",
                "gpu_name": str,
                "cpu_model": str,
                "total_memory_gb": float,
                "available_memory_gb": float,
                "memory_bandwidth_gbs": float,
                "disk_total_gb": float,
                "disk_available_gb": float,
                "estimated_tflops": float,
                "mlx_gpu_cores": int,
                "cpu_performance_units": float,
                "neural_engine_tops": float,
                "architecture": str,
                "global_inference_score": float,
                "global_inference_label": str,
                "global_finetuning_score": float,
                "global_finetuning_label": str,
                "gpu_score": float,
                "cpu_score": float,
                "memory_score": float,
                "unified_memory": True,
                "mps_available": bool,
                "system_platform": "Darwin",
                "mlx_chip_model": str,
                "performance_breakdown": dict
            }
            
        Raises:
            HardwareException: If evaluation fails critically.
            
        Examples:
            >>> eval_result = MLX_Engine.get_performance_evaluation()
            >>> print(f"Inference: {eval_result['global_inference_score']}/100")
            >>> print(f"Label: {eval_result['global_inference_label']}")
        """
        try:
            # Get base hardware info
            hw_info = cls.get_hardware_info()
            
            # Extract key metrics
            chip_model = hw_info.get("mlx_chip_model")
            gpu_cores = hw_info["gpu"]["mlx_gpu_cores"]
            estimated_tflops = hw_info["gpu"]["estimated_tflops"]
            memory_bandwidth = hw_info["gpu"]["memory_bandwidth_gbs"]
            neural_engine_tops = hw_info["accelerator"]["neural_engine_tops"]
            total_memory_gb = hw_info["memory"]["total_memory_gb"]
            available_memory_gb = hw_info["memory"]["available_memory_gb"]
            total_cores = hw_info["cpu"]["total_cores"]
            perf_cores = hw_info["cpu"].get("performance_cores", 4)
            
            # Calculate component scores (0-100 scale)
            
            # GPU/Accelerator score based on TFLOPS and GPU cores
            gpu_score = min(100, (estimated_tflops / 20.0) * 100)  # Normalize to 20 TFLOPS
            
            # Memory bandwidth score
            mem_bandwidth_score = min(100, (memory_bandwidth / 400.0) * 100)  # Normalize to 400 GB/s
            
            # Memory capacity score
            memory_capacity_score = min(100, (total_memory_gb / 64.0) * 100)  # Normalize to 64GB
            
            # Neural Engine score
            neural_score = min(100, (neural_engine_tops / 20.0) * 100)  # Normalize to 20 TOPS
            
            # CPU score based on performance cores
            cpu_performance_units = perf_cores * 2.5  # Weight performance cores higher
            cpu_score = min(100, (cpu_performance_units / 20.0) * 100)  # Normalize to 20 units
            
            # Calculate weighted inference score
            inference_score = (
                gpu_score * 0.35 +
                mem_bandwidth_score * 0.30 +
                memory_capacity_score * 0.20 +
                neural_score * 0.10 +
                cpu_score * 0.05
            )
            
            # Calculate weighted fine-tuning score
            finetuning_score = (
                memory_capacity_score * 0.40 +
                gpu_score * 0.25 +
                mem_bandwidth_score * 0.20 +
                neural_score * 0.10 +
                cpu_score * 0.05
            )
            
            # Generate labels based on scores
            def get_label(score: float) -> str:
                if score >= 80: return "Excellent"
                elif score >= 60: return "Good"
                elif score >= 40: return "Fair"
                elif score >= 20: return "Poor"
                else: return "Weak"
            
            inference_label = get_label(inference_score)
            finetuning_label = get_label(finetuning_score)
            
            # Build performance breakdown
            performance_breakdown = {
                "gpu_compute_score": round(gpu_score, 2),
                "memory_bandwidth_score": round(mem_bandwidth_score, 2),
                "memory_capacity_score": round(memory_capacity_score, 2),
                "neural_engine_score": round(neural_score, 2),
                "cpu_performance_score": round(cpu_score, 2),
                "weights_inference": {
                    "gpu_compute": 0.35,
                    "memory_bandwidth": 0.30,
                    "memory_capacity": 0.20,
                    "neural_engine": 0.10,
                    "cpu": 0.05
                },
                "weights_finetuning": {
                    "memory_capacity": 0.40,
                    "gpu_compute": 0.25,
                    "memory_bandwidth": 0.20,
                    "neural_engine": 0.10,
                    "cpu": 0.05
                }
            }
            
            # Build complete evaluation result
            eval_result = {
                # Hardware identification
                "backend_type": "mlx",
                "gpu_name": hw_info["gpu"]["gpu_name"],
                "cpu_model": hw_info["cpu"]["model"],
                
                # Memory metrics
                "total_memory_gb": total_memory_gb,
                "available_memory_gb": available_memory_gb,
                "memory_bandwidth_gbs": memory_bandwidth,
                
                # Storage metrics
                "disk_total_gb": hw_info["storage"]["total_gb"],
                "disk_available_gb": hw_info["storage"]["available_gb"],
                
                # Compute metrics
                "estimated_tflops": estimated_tflops,
                "mlx_gpu_cores": gpu_cores,
                "cpu_performance_units": cpu_performance_units,
                
                # Apple Silicon specific
                "neural_engine_tops": neural_engine_tops,
                "architecture": hw_info["accelerator"]["architecture"],
                "mlx_chip_model": chip_model,
                
                # Performance scores (0-100)
                "global_inference_score": round(inference_score, 2),
                "global_inference_label": inference_label,
                "global_finetuning_score": round(finetuning_score, 2),
                "global_finetuning_label": finetuning_label,
                "gpu_score": round(gpu_score, 2),
                "cpu_score": round(cpu_score, 2),
                "memory_score": round(memory_capacity_score, 2),
                
                # Technical details
                "unified_memory": True,
                "mps_available": hw_info["gpu"]["mps_supported"],
                "system_platform": hw_info["system"]["platform"],
                
                # Performance breakdown
                "performance_breakdown": performance_breakdown
            }
            
            logging.info(f"Performance evaluation: Inference={inference_score:.1f}/100 ({inference_label}), Fine-tuning={finetuning_score:.1f}/100 ({finetuning_label})")
            return eval_result
            
        except Exception as e:
            logging.exception(f"Performance evaluation failed: {e}")
            raise HardwareException(
                "Failed to evaluate Apple Silicon performance",
                trace=str(e)
            )

    @classmethod
    def get_flat_hardware_data(cls) -> Dict[str, Any]:
        """Get hardware data in flat format compatible with HardwareProfile entity.
        
        Returns hardware specifications as a flat dictionary ready for database
        insertion. For MLX backend, get_performance_evaluation() already returns
        data in the correct flat format.
        
        Returns:
            Flat dict with all fields matching HardwareProfile columns.
            
        Raises:
            HardwareException: If hardware data collection fails.
        """
        # get_performance_evaluation() already returns flat structure
        return cls.get_performance_evaluation()
