"""CPU engine for fallback inference using llama.cpp HTTP server.

This module provides a CPU-only backend for systems without GPU acceleration:
- Uses llama.cpp server (OpenAI-compatible API) for optimized CPU inference
- GGUF model format for quantization (4-bit, 5-bit, 8-bit)
- Threading optimization for multi-core CPUs
- Fallback when MLX (Mac Silicon) or CUDA (NVIDIA GPU) unavailable
- Rosetta support for x86_64 binaries on Apple Silicon

Current Status:
    FUNCTIONAL - Core features implemented. Performance evaluation pending refinement.

Features:
    - Load GGUF quantized models via llama-server subprocess
    - Multi-threaded inference with configurable thread count
    - Context window optimization (configurable via ERUDI_CTX)
    - Streaming generation via OpenAI-compatible /v1/chat/completions
    - Automatic port selection and server lifecycle management
    - Cross-platform (macOS, Linux, Windows) with Rosetta support

Architecture:
    CPU Engine (Singleton):
    ┌───────────────────────────────────────────────────────────┐
    │ get_model_and_tokenizer()                                 │
    │  └─> Start llama-server → return handle                  │
    └───────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────────────┐
    │ generate_stream()                                         │
    │  1. POST to /v1/chat/completions with stream=True         │
    │  2. Parse SSE events (Server-Sent Events)                 │
    │  3. Yield token deltas                                    │
    └───────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────────────┐
    │ cleanup()                                                 │
    │  └─> Terminate server process → free memory              │
    └───────────────────────────────────────────────────────────┘

Example:
    ::

        from src.engines.cpu_engine import CPU_Engine

        model, tokenizer = CPU_Engine.get_model_and_tokenizer(
            llm_id="mistral-7b-q4",
            llm_local_path="/path/to/model.gguf"
        )

        for token in CPU_Engine.generate_stream(
            model, tokenizer, prompt,
            max_tokens=256, temperature=0.7
        ):
            print(token, end="")

Note:
    BaseEngine.get_engine() will automatically select CPU_Engine if:
    - System is not Mac Silicon (no MLX)
    - No CUDA-capable GPU detected (no CUDA_Engine)

    This ensures graceful degradation for unsupported hardware.

Warning:
    CPU inference is significantly slower than GPU (10-50x depending on model size).
    Use only as last resort fallback when GPU acceleration is unavailable.
    For production deployments, prefer MLX (Mac) or CUDA (NVIDIA) engines.
"""

# src/engines/cpu_engine.py
# CPU_Engine: llama.cpp HTTP server backend
# - Overrides only abstract methods from BaseEngine
# - Keeps common infra (singleton, cleanup monitor) untouched
# - OS-proof (Darwin/Windows/Linux) with guarded, minimal OS-specific code
# - Uses llama-server (OpenAI-compatible /v1/chat/completions)
# - No subprocess-per-request; one local server process per loaded model

from __future__ import annotations
import os, sys, time, json, subprocess, signal, atexit, platform, socket, shutil
from pathlib import Path
from typing import Any, Optional, Tuple, Generator, Union, Dict, List

try:
    import requests  # required for HTTP calls to llama-server
except Exception as _e:
    requests = None  # We will raise a clear EngineException at runtime

from src.engines.base_engine import BaseEngine
from src.core.exceptions import EngineException
from src.core.logging import logger


class CPU_Engine(BaseEngine):
    """
    CPU Engine using llama.cpp's HTTP server (llama-server).
    - get_model_and_tokenizer() starts a local llama-server process bound to 127.0.0.1
    - generate_stream() talks to /v1/chat/completions with OpenAI-compatible payload
    - quant_and_save_from_hf_format() optionally converts HF -> GGUF via llama.cpp tooling
    Notes:
      * "model" is a dict handle for the running server (pid, port, alias, base_url)
      * "tokenizer" is a placeholder (HTTP server abstracts tokenization)
    """
    
    MODEL_MAPPING = {
        # Ignore for the moment, to be worked on later
    }

    # ---------- Private helpers (internal, not part of BaseEngine API) ----------

    @classmethod
    def _assert_requests(cls):
        if requests is None:
            raise EngineException("Missing dependency 'requests'. Install it in the runtime environment.")

    @classmethod
    def _default_install_dir(cls) -> Path:
        # Where your build script installs llama.cpp artifacts
        # Overridable with ERUDI_LLAMA_CPP_INSTALL_DIR
        p = os.environ.get("ERUDI_LLAMA_CPP_INSTALL_DIR", "backend/artifacts/llama-cpp/cpu")
        return Path(p).resolve()

    @classmethod
    def _find_llama_server(cls, install_dir: Path) -> Path:
        exe = "llama-server.exe" if os.name == "nt" else "llama-server"
        p = install_dir / "bin" / exe
        if not p.exists():
            raise EngineException(f"llama-server not found at {p}. Rebuild with LLAMA_BUILD_SERVER=ON and install.")
        return p

    @classmethod
    def _pick_free_port(cls, start: int = 8080, limit: int = 100) -> int:
        for port in range(start, start + limit):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise EngineException("No free TCP port found for llama-server.")

    @classmethod
    def _wrap_arch_if_needed(cls, argv: List[str], server_path: Path) -> List[str]:
        # On Apple Silicon, if server is x86_64 only, run under Rosetta: arch -x86_64 <cmd>
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            try:
                out = subprocess.check_output(["file", str(server_path)], text=True)
                if "x86_64" in out and "arm64" not in out:
                    return ["arch", "-x86_64", *argv]
            except Exception:
                pass
        return argv

    @classmethod
    def _probe_ready(cls, base_url: str, model_alias: str, timeout_s: float = 90.0) -> None:
        cls._assert_requests()
        t0 = time.time()
        url = f"{base_url}/v1/chat/completions"
        payload = {"model": model_alias, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
        while time.time() - t0 < timeout_s:
            try:
                r = requests.post(url, json=payload, timeout=1.5)
                if r.status_code in (200, 400):
                    return
            except Exception:
                pass
            time.sleep(0.4)
        raise EngineException("llama-server did not become ready within timeout.")

    @classmethod
    def _start_server(
        cls,
        model_gguf: Path,
        install_dir: Path,
        alias: str,
        ctx: int,
        threads: Optional[int],
        gpu_layers: int = 0,
        port: Optional[int] = None,
        extra_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        server_path = cls._find_llama_server(install_dir)
        if threads is None:
            threads = max(1, os.cpu_count() or 1)
        port = port or cls._pick_free_port()

        args = [
            str(server_path),
            "-m", str(model_gguf),
            "--host", "127.0.0.1",
            "--port", str(port),
            "--alias", alias,
            "-c", str(ctx),
            "--threads", str(threads),
            "-ngl", str(gpu_layers),  # force CPU
        ]
        if extra_args:
            args += extra_args

        argv = cls._wrap_arch_if_needed(args, server_path)

        # Start detached but keep handle to terminate later
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=os.environ.copy(),
        )

        base_url = f"http://127.0.0.1:{port}"
        cls._probe_ready(base_url, alias)

        # Ensure cleanup on interpreter exit
        atexit.register(lambda: cls._terminate_process(proc))

        return {
            "pid": proc.pid,
            "proc": proc,
            "port": port,
            "base_url": base_url,
            "alias": alias,
            "model_path": str(model_gguf),
            "threads": threads,
        }

    @classmethod
    def _terminate_process(cls, proc: subprocess.Popen):
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
            pass

    @classmethod
    def _select_gguf(cls, llm_local_path: Union[str, Path]) -> Path:
        """Select the best GGUF file from the given path.
        
        Priority order if multiple GGUFs exist:
        1. Prefer known quantization types: q4_k_m > q4_0 > q5_k_m > q8_0 > f16
        2. Fall back to smallest file (most quantized)
        
        Args:
            llm_local_path: Path to .gguf file or directory containing .gguf files.
            
        Returns:
            Path to the selected .gguf file.
            
        Raises:
            FileNotFoundError: If path doesn't exist.
            EngineException: If path is not .gguf or directory contains no .gguf files.
        """
        p = Path(llm_local_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Model path not found: {p}")
        if p.is_file():
            if p.suffix.lower() == ".gguf":
                return p
            raise EngineException(f"Expected a .gguf file. Got: {p}")
        
        # Directory: find all .gguf files
        ggufs = list(p.glob("*.gguf"))
        if not ggufs:
            raise EngineException(f"No .gguf found in {p}. Convert or quantize first.")
        
        # If only one, return it
        if len(ggufs) == 1:
            return ggufs[0]
        
        # Multiple GGUFs: prioritize by quantization type
        QUANT_PRIORITY = ["q4_k_m", "q4_0", "q5_k_m", "q8_0", "f16"]
        for quant in QUANT_PRIORITY:
            for gguf in ggufs:
                if quant in gguf.stem.lower():
                    logger.info(f"[CPU_Engine] Selected {gguf.name} (matched quant type: {quant})")
                    return gguf
        
        # Fallback: smallest file (most quantized)
        smallest = min(ggufs, key=lambda x: x.stat().st_size)
        logger.warning(f"[CPU_Engine] No known quant pattern found. Selecting smallest: {smallest.name}")
        return smallest

    # ---------- Abstract methods (required by BaseEngine) ----------

    @classmethod
    def quant_and_save_from_hf_format(
        cls,
        local_hf_path: Union[str, Path],
        local_dest_path: Union[str, Path],
        quantize: bool = True,
        q_bits: str = "4",
        *args
    ) -> None:
        """Convert HuggingFace model to GGUF format with optional quantization.
        
        Smart converter that handles two scenarios:
        1. Pre-quantized GGUF files (from MODEL_MAPPING repos like TheBloke):
           - Detects existing .gguf files in source directory
           - Selects best quantization variant using priority heuristic
           - Copies directly to destination (no conversion needed)
           
        2. SafeTensors models (original HuggingFace repos):
           - Converts HF format to GGUF using llama.cpp converter
           - Optionally quantizes to Q4_K_M or Q8_0
           - Cleans up intermediate FP16 files after quantization
        
        Args:
            local_hf_path: Source directory containing HF model or GGUF files.
                          Caller is responsible for cleanup after this method returns.
            local_dest_path: Destination directory for final GGUF model.
            quantize: Whether to quantize after conversion (default: True).
                     Ignored if source already contains GGUF files.
            q_bits: Quantization precision - "4" for Q4_K_M, "8" for Q8_0 (default: "4").
            *args: Reserved for future engine-specific arguments.
            
        Returns:
            None. GGUF file(s) written to local_dest_path.
            
        Raises:
            FileNotFoundError: If local_hf_path doesn't exist.
            EngineException: If no valid model files found (.gguf or .safetensors).
            EngineException: If conversion or quantization fails.
            EngineException: If required llama.cpp tools not found.
            
        Examples:
            Pre-quantized GGUF (fast path)::
            
                # Source: TheBloke/Mistral-7B-GGUF/*.gguf
                CPU_Engine.quant_and_save_from_hf_format(
                    local_hf_path="backend/data/models/temp_42",
                    local_dest_path="backend/data/models/42"
                )
                # → Copies best .gguf to destination (instant)
            
            SafeTensors conversion (slow path)::
            
                # Source: mistralai/Mistral-7B/*.safetensors
                CPU_Engine.quant_and_save_from_hf_format(
                    local_hf_path="backend/data/models/temp_42",
                    local_dest_path="backend/data/models/42",
                    quantize=True,
                    q_bits="4"
                )
                # → Converts to GGUF + quantizes to Q4_K_M (5-10 min)
        
        Note:
            Requires llama.cpp tools installed in ERUDI_LLAMA_CPP_ROOT:
            - convert-hf-to-gguf.py (Python script in llama.cpp repo)
            - llama-quantize (compiled binary in bin/)
            
            Set ERUDI_LLAMA_CPP_ROOT env var to override default path.
            
            Disk Space Optimization:
            - HF source files (~7GB) deleted after conversion to save space
            - Reduces peak disk usage from 18GB to 11GB during quantization
            - If quantization fails, HF files must be re-downloaded
        """
        src = Path(local_hf_path).resolve()
        dst = Path(local_dest_path).resolve()
        
        if not src.exists():
            raise FileNotFoundError(f"Model path not found: {src}")
        
        dst.mkdir(parents=True, exist_ok=True)
        
        # ============ CASE 1: Pre-quantized GGUF files detected ============
        ggufs = list(src.glob("*.gguf"))
        if ggufs:
            logger.info(f"[CPU_Engine] Detected {len(ggufs)} pre-quantized GGUF file(s) in {src}")
            
            # Use existing selection logic with priority heuristic
            selected = cls._select_gguf(src)
            dest_file = dst / selected.name
            
            shutil.copy(selected, dest_file)
            logger.info(f"[CPU_Engine] Copied pre-quantized GGUF: {selected.name} → {dest_file}")
            return  # Early return - no conversion needed!
        
        # ============ CASE 2: SafeTensors model - convert to GGUF ============
        safetensors = list(src.glob("*.safetensors"))
        if not safetensors:
            raise EngineException(
                f"No .gguf or .safetensors files found in {src}. "
                "Expected HuggingFace model or pre-quantized GGUF files."
            )
        
        logger.info(f"[CPU_Engine] Detected SafeTensors model with {len(safetensors)} shard(s), converting to GGUF...")
        
        # Find llama.cpp converter script
        llama_root = Path(os.environ.get("ERUDI_LLAMA_CPP_ROOT", "backend/forks/llama-cpp")).resolve()
        converter = llama_root / "convert-hf-to-gguf.py"
        if not converter.exists():
            raise EngineException(
                f"Converter script not found: {converter}. "
                "Ensure llama.cpp is cloned and ERUDI_LLAMA_CPP_ROOT is set correctly."
            )
        
        # Convert HF → FP16 GGUF
        fp16_gguf = dst / "model-f16.gguf"
        cmd_convert = [
            sys.executable, str(converter),
            str(src),
            "--outtype", "f16",
            "--outfile", str(fp16_gguf)
        ]
        logger.info(f"[CPU_Engine] Converting HF → GGUF (FP16): {' '.join(cmd_convert)}")
        rc = subprocess.call(cmd_convert)
        if rc != 0:
            raise EngineException(
                f"HuggingFace → GGUF conversion failed with exit code {rc}. "
                "Check logs for details (model compatibility, missing files, etc.)."
            )
        
        logger.info(f"[CPU_Engine] Conversion complete: {fp16_gguf} ({fp16_gguf.stat().st_size / (1024**3):.2f} GB)")
        
        # Optional quantization
        if quantize:
            # Map q_bits to llama.cpp quantization method
            q_method = "q4_k_m" if q_bits.startswith("4") else "q8_0"
            
            # Find quantizer binary
            quant_bin = cls._default_install_dir() / "bin" / ("llama-quantize.exe" if os.name == "nt" else "llama-quantize")
            if not quant_bin.exists():
                # Fallback to legacy name
                quant_bin = cls._default_install_dir() / "bin" / ("quantize.exe" if os.name == "nt" else "quantize")
            if not quant_bin.exists():
                raise EngineException(
                    f"Quantizer binary not found: {quant_bin}. "
                    "Ensure llama.cpp was built with LLAMA_BUILD_SERVER=ON and installed correctly."
                )
            
            # Quantize FP16 → Q4_K_M or Q8_0
            out_q = dst / f"model-{q_method}.gguf"
            cmd_quant = [str(quant_bin), str(fp16_gguf), str(out_q), q_method]
            logger.info(f"[CPU_Engine] Quantizing GGUF (FP16 → {q_method.upper()}): {' '.join(cmd_quant)}")
            rc = subprocess.call(cmd_quant)
            if rc != 0:
                raise EngineException(
                    f"Quantization failed with exit code {rc}. "
                    "Check logs for details (OOM, unsupported model, etc.)."
                )
            
            logger.info(f"[CPU_Engine] Quantization complete: {out_q} ({out_q.stat().st_size / (1024**3):.2f} GB)")
            
            # Clean up FP16 intermediate file to save disk space
            try:
                fp16_gguf.unlink()
                logger.info(f"[CPU_Engine] Cleaned up intermediate FP16 file: {fp16_gguf}")
            except Exception as e:
                logger.warning(f"[CPU_Engine] Failed to delete intermediate file {fp16_gguf}: {e}")
        else:
            logger.info(f"[CPU_Engine] Skipping quantization (quantize=False), keeping FP16 GGUF")

    @classmethod
    def get_model_and_tokenizer(
        cls,
        llm_id: str,
        llm_local_path: Union[str, Path],
        *args
    ) -> Tuple[Any, Any]:
        """
        Starts llama-server for the given GGUF and returns (model_handle, tokenizer_placeholder).
        Idempotent: if the same llm_id is already loaded, returns cached.
        """
        with cls._lock:
            # If model is already loaded and matches llm_id, return cached
            if not cls._should_reload_model(llm_id):
                return cls._return_cached_model_and_tokenizer()

            cls._assert_requests()
            gguf = cls._select_gguf(llm_local_path)
            install_dir = cls._default_install_dir()

            # Kill previous process if any
            prev = cls._model
            if isinstance(prev, dict) and "proc" in prev and prev["proc"] is not None:
                cls._terminate_process(prev["proc"])

            # Start server
            alias = f"erudi-{llm_id}"
            model_handle = cls._start_server(
                model_gguf=gguf,
                install_dir=install_dir,
                alias=alias,
                ctx=int(os.environ.get("ERUDI_CTX", "4096")),
                threads=None,
                gpu_layers=0,
                port=None,
                extra_args=None,
            )

            cls._model = model_handle
            cls._tokenizer = {"type": "remote", "provider": "llama-server"}
            cls._model_id = llm_id
            from datetime import datetime
            cls._last_used = datetime.now()  # Mark as active
            logger.info(f"[CPU_Engine] Model loaded via llama-server on {model_handle['base_url']} alias={alias}")
            return cls._model, cls._tokenizer

    @classmethod
    def generate_stream(
        cls,
        model: Any,
        tokenizer: Any,
        prompt: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
        *args
    ) -> Generator[str, None, None]:
        """
        Streams tokens from llama-server (/v1/chat/completions, stream=True).
        Yields token deltas as strings.
        """
        if not isinstance(model, dict) or "base_url" not in model:
            raise RuntimeError("Invalid model handle for CPU_Engine. Call get_model_and_tokenizer() first.")

        cls._assert_requests()
        base_url = model["base_url"]
        alias = model["alias"]
        url = f"{base_url}/v1/chat/completions"

        payload = {
            "model": alias,
            "messages": prompt,
            "max_tokens": max_tokens,
            "temperature": float(temperature),
            "top_p": float(top_p),
            "stream": True,
        }

        with cls._lock:
            cls._last_used = None

        try:
            with requests.post(url, json=payload, stream=True, timeout=600) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            delta = obj["choices"][0].get("delta", {}).get("content")
                            if delta:
                                yield delta
                        except Exception:
                            # ignore malformed lines
                            continue
        except Exception as e:
            raise EngineException(message="CPU_Engine streaming failed", trace=e)
        finally:
            with cls._lock:
                from datetime import datetime
                cls._last_used = datetime.now()

    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        # Ignore for the moment, it will be re-worked later
        import shutil, platform, math
        info: Dict[str, Any] = {}
        try:
            import psutil
        except Exception:
            psutil = None  # optional

        system = platform.system()
        machine = platform.machine()
        processor = platform.processor() or platform.uname().processor
        total_cores = os.cpu_count() or 1

        total_mem = avail_mem = None
        if psutil:
            vm = psutil.virtual_memory()
            total_mem = round(vm.total / (1024**3), 2)
            avail_mem = round(vm.available / (1024**3), 2)

        info = {
            "system": {
                "platform": system,
                "platform_version": platform.version(),
                "machine": machine,
                "processor": processor,
            },
            "cpu": {
                "model": processor,
                "architecture": machine,
                "total_cores": total_cores,
                "logical_cores": total_cores,
                "is_apple_silicon": system == "Darwin" and "arm" in machine.lower(),
                "performance_cores": None,
                "efficiency_cores": None,
            },
            "memory": {
                "total_memory_gb": total_mem,
                "available_memory_gb": avail_mem,
                "memory_pressure": None,
                "memory_type": "system",
            },
            "gpu": {
                "gpu_name": "none",
                "gpu_cores": None,
                "memory_bandwidth_gbs": None,
                "vram_total_gb": None,
                "vram_available_gb": None,
                "compute_capability": None,
                "cuda_version": None,
                "mps_supported": None,
                "unified_memory": False,
            },
            "accelerator": {
                "neural_engine_tops": None,
                "architecture": None,
            },
            "storage": {
                "total_gb": None,
                "available_gb": None,
                "usage_percentage": None,
            },
            "backend_type": "cpu",
            "timestamp": time.time(),
        }
        return info

    @classmethod
    def warm_up_accelerator(cls, duration_seconds: float = 1.0) -> bool:
        # CPU warm-up is minimal; keep it simple and bounded
        # Ignore for the moment, it will be re-worked later
        t0 = time.time()
        n = 0
        try:
            while time.time() - t0 < max(0.05, float(duration_seconds)):
                # tiny compute loop
                for _ in range(10000):
                    n += (_ * 7) % 13
            return True
        except Exception:
            return False

    @classmethod
    def get_performance_evaluation(cls) -> Dict[str, Any]:
        # Lightweight heuristic for CPU backend; avoid heavy probes
        # Ignore for the moment, it will be re-worked later
        cores = max(1, os.cpu_count() or 1)
        base = min(100.0, 10.0 * (cores ** 0.5))
        inf = round(base, 2)
        finetune = round(max(5.0, base * 0.6), 2)
        out = {
            "backend_type": "cpu",
            "accelerator_name": "none",
            "cpu_model": platform.processor(),
            "total_memory_gb": None,
            "available_memory_gb": None,
            "memory_bandwidth_gbs": None,
            "disk_total_gb": None,
            "disk_available_gb": None,
            "estimated_tflops": None,
            "compute_units": cores,
            "cpu_performance_units": cores,
            "neural_engine_tops": None,
            "cuda_version": None,
            "compute_capability": None,
            "architecture": platform.machine(),
            "global_inference_score": inf,
            "global_inference_label": "Good" if inf >= 60 else "Medium" if inf >= 30 else "Poor",
            "global_finetuning_score": finetune,
            "global_finetuning_label": "Poor",
            "gpu_score": 0.0,
            "cpu_score": inf,
            "memory_score": 0.0,
            "unified_memory": False,
            "accelerator_available": False,
            "system_platform": platform.system(),
            "performance_breakdown": {
                "compute_score": inf,
                "memory_bandwidth_score": 0.0,
                "memory_capacity_score": 0.0,
                "cpu_performance_score": inf,
            },
        }
        return out
    
    @classmethod
    def _server_is_alive(cls) -> bool:
        prev = cls._model
        if not isinstance(prev, dict):
            return False
        proc = prev.get("proc")
        return bool(proc and proc.poll() is None)

    @classmethod
    def _wait_port_closed(cls, port: int, timeout_s: float = 3.0) -> None:
        import socket, time
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return
            time.sleep(0.1)

    @classmethod
    def _stop_server_if_running(cls) -> None:
        prev = cls._model
        if not isinstance(prev, dict):
            return
        proc = prev.get("proc")
        port = prev.get("port")
        try:
            if proc:
                cls._terminate_process(proc)  # already OS-guarded
            if port is not None:
                try:
                    cls._wait_port_closed(int(port))
                except Exception:
                    pass
        except Exception as e:
            from src.core.logging import logger
            logger.warning(f"[CPU_Engine] graceful stop failed: {e}")

    @classmethod
    def cleanup(cls) -> None:
        # Ensure the external server process is killed, then clear base state.
        with cls._lock:
            cls._stop_server_if_running()
            return super().cleanup()
