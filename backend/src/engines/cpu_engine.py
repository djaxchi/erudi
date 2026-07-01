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
    │ token streaming lives in the agent layer, not the engine: │
    │   AgentRunner → ChatOpenAI(base_url) → POST /v1/chat/...  │
    │   the engine only spawns / probes / reaps the server      │
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

        # Token streaming is driven by the agent layer (ChatOpenAI(base_url=...)),
        # not the engine; ``model["base_url"]`` is what it connects to.

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
import os
import sys
import platform
import shutil
import subprocess  # used by quant_and_save_from_hf_format + hardware probes
import time  # used by hardware warm-up loop
from pathlib import Path
from typing import Any, Dict, List, Union

from src.engines.base_llama_cpp_engine import BaseLlamaCppEngine
from src.core.exceptions import EngineException
from src.core.logging import logger
from src.core.config import ROOT_DIR


class CPU_Engine(BaseLlamaCppEngine):
    """
    CPU Engine using llama.cpp's HTTP server (llama-server).

    Inherits the subprocess + SSE lifecycle from BaseChatServerEngine and the
    llama-cpp specifics (Popen, GGUF picking, llama-server location) from
    BaseLlamaCppEngine. Only `_build_spawn_argv` + `_prepare_spawn_context`
    + class attrs are CPU-specific here.

    Notes:
      * "model" is a dict handle for the running server (pid, port, alias, base_url)
      * "tokenizer" is a placeholder (HTTP server abstracts tokenization)
    """

    # --- BaseChatServerEngine config overrides ---
    _server_name = "llama-server"
    _tokenizer_provider = "llama-server"
    # _port_range_start = 27200 (inherited from BaseLlamaCppEngine)
    # _use_cuda_build = False (inherited from BaseLlamaCppEngine)
    # USES_GGUF + MODEL_MAPPING (public-GGUF catalog) inherited from BaseLlamaCppEngine.

    # ---------- CPU-specific spawn hooks ----------

    @classmethod
    def _prepare_spawn_context(cls) -> Dict[str, Any]:
        """Resolve the per-spawn CPU context: context window, thread count,
        and the fixed `gpu_layers=0` (CPU-only inference)."""
        return {
            "ctx_size": int(os.environ.get("ERUDI_CTX", "4096")),
            "threads": max(1, os.cpu_count() or 1),
            "gpu_layers": 0,
        }

    @classmethod
    def _build_spawn_argv(
        cls,
        *,
        llama_server: Path,
        model_gguf: Path,
        alias: str,
        port: int,
        ctx_size: int = 4096,
        threads: int = 1,
        gpu_layers: int = 0,
        **_ignored: Any,
    ) -> List[Any]:
        """CPU CLI for llama-server: forces `-ngl 0`, sized context, native threads.

        ``--jinja`` enables the model's own chat template and with it
        OpenAI-style function calling (the agent's calculator tool) —
        without it llama-server never emits ``tool_calls``.
        """
        return [
            str(llama_server),
            "-m", str(model_gguf),
            "--host", "127.0.0.1",
            "--port", str(port),
            "--alias", alias,
            "-c", str(ctx_size),
            "--threads", str(threads),
            "-ngl", str(gpu_layers),
            "--jinja",
        ]

    @classmethod
    def _copy_auxiliary_files(cls, src: Path, dst: Path) -> None:
        """Copy auxiliary files from source to destination, excluding .safetensors and .model files.
        
        Args:
            src: Source directory path.
            dst: Destination directory path.
        """
        excluded_extensions = {'.safetensors', '.model', '.gguf'}
        for file_path in src.iterdir():
            if file_path.is_file() and file_path.suffix.lower() not in excluded_extensions:
                shutil.copy(file_path, dst / file_path.name)
                logger.debug(f"[CPU_Engine] Copied auxiliary file: {file_path.name}")

    @classmethod
    def _run_converter_inprocess(cls, converter: Path, install_dir: Path, src: Path, fp16_gguf: Path) -> int:
        """Run convert_hf_to_gguf.py in-process (required in PyInstaller frozen mode where
        sys.executable is backend.exe, not a Python interpreter)."""
        import importlib.util
        gguf_pkg = install_dir / "gguf-py"
        extra_paths = [str(gguf_pkg), str(install_dir)]
        saved_argv = sys.argv[:]
        saved_path = sys.path[:]
        for p in reversed(extra_paths):
            if p not in sys.path:
                sys.path.insert(0, p)
        sys.argv = [str(converter), str(src), "--outtype", "f16", "--outfile", str(fp16_gguf)]
        try:
            spec = importlib.util.spec_from_file_location("convert_hf_to_gguf", str(converter))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.main()
            return 0
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
            if code != 0:
                logger.error(f"[CPU_Engine] Converter exited with code {code}")
            return int(code)
        except Exception as exc:
            logger.error(f"[CPU_Engine] In-process conversion failed: {exc}")
            return 1
        finally:
            sys.argv = saved_argv
            sys.path = saved_path
            for key in list(sys.modules.keys()):
                if "convert_hf_to_gguf" in key or key == "gguf" or key.startswith("gguf."):
                    sys.modules.pop(key, None)

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
            None. GGUF file(s) and auxiliary files written to local_dest_path.
            
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
            Requires llama.cpp tools installed :
            - convert_hf_to_gguf.py (Python script in llama.cpp repo)
            - llama-quantize (compiled binary in bin/)
            
            Auxiliary files (JSON configs, tokenizer files, etc.) are copied to destination,
            excluding .safetensors and .model files.
            
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
            cls._copy_auxiliary_files(src, dst)
            return  # Early return - no conversion needed!
        
        # ============ CASE 2: SafeTensors model - convert to GGUF ============
        safetensors = list(src.glob("*.safetensors"))
        if not safetensors:
            raise EngineException(
                f"No .gguf or .safetensors files found in {src}. "
                "Expected HuggingFace model or pre-quantized GGUF files."
            )
        
        logger.info(f"[CPU_Engine] Detected SafeTensors model with {len(safetensors)} shard(s), converting to GGUF...")
        
        # Find llama.cpp converter script (engine-agnostic — fall back to cuda bin)
        converter = cls._default_install_dir() / "convert_hf_to_gguf.py"
        if not converter.exists():
            fallback = ROOT_DIR / "artifacts" / "llama-cpp" / "cuda" / "bin" / "convert_hf_to_gguf.py"
            if fallback.exists():
                converter = fallback
            else:
                raise EngineException(
                    f"Converter script not found: {converter}. "
                    f"Ensure llama.cpp is cloned, built and scripts installed at {cls._default_install_dir()}."
                )
        
        # Convert HF → FP16 GGUF
        fp16_gguf = dst / "model-f16.gguf"
        install_dir = converter.parent
        if getattr(sys, 'frozen', False):
            logger.info(f"[CPU_Engine] Converting HF → GGUF (FP16) in-process: {converter}")
            rc = cls._run_converter_inprocess(converter, install_dir, src, fp16_gguf)
        else:
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
            
            # Find quantizer binary (fall back to cuda bin if cpu bin absent)
            _qname = "llama-quantize.exe" if os.name == "nt" else "llama-quantize"
            _qlegacy = "quantize.exe" if os.name == "nt" else "quantize"
            quant_bin = cls._default_install_dir() / _qname
            if not quant_bin.exists():
                quant_bin = cls._default_install_dir() / _qlegacy
            if not quant_bin.exists():
                quant_bin = ROOT_DIR / "artifacts" / "llama-cpp" / "cuda" / "bin" / _qname
            if not quant_bin.exists():
                raise EngineException(
                    f"Quantizer binary not found: {quant_bin}. "
                    "Ensure llama.cpp was built and installed correctly."
                )
            
            # Quantize FP16 → Q4_K_M or Q8_0
            out_q = dst / f"model-{q_method}.gguf"
            out_q_tmp = dst / f"model-{q_method}.gguf.tmp"
            cmd_quant = [str(quant_bin), str(fp16_gguf), str(out_q_tmp), q_method]
            logger.info(f"[CPU_Engine] Quantizing GGUF (FP16 → {q_method.upper()}): {' '.join(cmd_quant)}")
            rc = subprocess.call(cmd_quant)
            if rc != 0:
                out_q_tmp.unlink(missing_ok=True)
                raise EngineException(
                    f"Quantization failed with exit code {rc}. "
                    "Check logs for details (OOM, unsupported model, etc.)."
                )
            # Atomic rename: file only appears at final path when fully written
            out_q_tmp.rename(out_q)
            logger.info(f"[CPU_Engine] Quantization complete: {out_q} ({out_q.stat().st_size / (1024**3):.2f} GB)")
            
            # Clean up FP16 intermediate file to save disk space
            try:
                fp16_gguf.unlink()
                logger.info(f"[CPU_Engine] Cleaned up intermediate FP16 file: {fp16_gguf}")
            except Exception as e:
                logger.warning(f"[CPU_Engine] Failed to delete intermediate file {fp16_gguf}: {e}")
        else:
            logger.info("[CPU_Engine] Skipping quantization (quantize=False), keeping FP16 GGUF")
        
        cls._copy_auxiliary_files(src, dst)

    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        """Get comprehensive hardware information for CPU-only backend.
        
        Returns detailed hardware specifications including CPU model, system memory,
        storage capacity, and platform information. No GPU/accelerator data.
        
        Returns:
            Dict containing hardware specifications following BaseEngine contract:
            {
                "system": {"platform": str, "platform_version": str, ...},
                "cpu": {"model": str, "total_cores": int, "architecture": str, ...},
                "memory": {"total_memory_gb": float, "available_memory_gb": float, ...},
                "storage": {"total_gb": float, "available_gb": float, "usage_percentage": float},
                "backend_type": "cpu",
                "timestamp": float
            }
            
        Note:
            GPU fields return None/False since this is CPU-only backend.
            Falls back gracefully if psutil/cpuinfo unavailable.
        """
        try:
            # Import optional dependencies for hardware detection
            try:
                import psutil
                import cpuinfo
            except ImportError as e:
                logger.warning(f"Optional hardware detection dependency missing: {e}")
                psutil = None
                cpuinfo = None

            # System information
            system = platform.system()
            machine = platform.machine()
            processor = platform.processor() or platform.uname().processor
            
            # CPU information
            total_cores = psutil.cpu_count(logical=False) if psutil else (os.cpu_count() or 1)
            logical_cores = psutil.cpu_count(logical=True) if psutil else (os.cpu_count() or 1)
            
            # Enhanced CPU model detection using cpuinfo
            cpu_model = processor
            cpu_brand = None
            if cpuinfo:
                cpu_info_data = cpuinfo.get_cpu_info()
                cpu_brand = cpu_info_data.get("brand_raw")
                if cpu_brand:
                    cpu_model = cpu_brand
            
            # Check if Apple Silicon (shouldn't normally reach CPU_Engine on Mac, but handle it)
            is_apple_silicon = system == "Darwin" and "arm" in machine.lower()
            
            # Memory information
            total_mem = avail_mem = memory_pressure = None
            if psutil:
                vm = psutil.virtual_memory()
                total_mem = round(vm.total / (1024**3), 2)
                avail_mem = round(vm.available / (1024**3), 2)
                memory_pressure = round(1.0 - (vm.available / vm.total), 3) if vm.total > 0 else 0.0
            
            # Storage information
            disk_total = disk_available = disk_usage_pct = None
            if psutil:
                try:
                    disk = psutil.disk_usage(os.path.abspath(os.sep))
                    disk_total = round(disk.total / (1024**3), 2)
                    disk_available = round(disk.free / (1024**3), 2)
                    disk_usage_pct = round(disk.percent, 2)
                except Exception as e:
                    logger.warning(f"Failed to get disk info: {e}")
            
            # Build hardware info dictionary
            info = {
                "system": {
                    "platform": system,
                    "platform_version": platform.version(),
                    "machine": machine,
                    "processor": processor,
                },
                "cpu": {
                    "model": cpu_model,
                    "architecture": machine,
                    "total_cores": total_cores,
                    "logical_cores": logical_cores,
                    "is_apple_silicon": is_apple_silicon,
                    "performance_cores": None,  # Not available without Apple Silicon API
                    "efficiency_cores": None,
                },
                "memory": {
                    "total_memory_gb": total_mem,
                    "available_memory_gb": avail_mem,
                    "memory_pressure": memory_pressure,
                    "memory_type": "system",
                },
                "gpu": {
                    "gpu_name": "CPU Only",
                    "gpu_cores": None,
                    "memory_bandwidth_gbs": None,
                    "vram_total_gb": None,
                    "vram_available_gb": None,
                    "compute_capability": None,
                    "cuda_version": None,
                    "mps_supported": False,
                    "unified_memory": False,
                },
                "accelerator": {
                    "neural_engine_tops": None,
                    "architecture": None,
                },
                "storage": {
                    "total_gb": disk_total,
                    "available_gb": disk_available,
                    "usage_percentage": disk_usage_pct,
                },
                "backend_type": "cpu",
                "timestamp": time.time(),
            }
            
            logger.info(f"CPU hardware detected: {cpu_model}, {total_cores} cores, {total_mem}GB RAM")
            return info
            
        except Exception as e:
            logger.exception(f"CPU hardware detection failed: {e}")
            # Return minimal fallback info
            return {
                "system": {"platform": platform.system(), "platform_version": platform.version(), 
                          "machine": platform.machine(), "processor": "Unknown"},
                "cpu": {"model": "Unknown CPU", "architecture": platform.machine(), 
                       "total_cores": os.cpu_count() or 1, "logical_cores": os.cpu_count() or 1,
                       "is_apple_silicon": False, "performance_cores": None, "efficiency_cores": None},
                "memory": {"total_memory_gb": None, "available_memory_gb": None, 
                          "memory_pressure": None, "memory_type": "system"},
                "gpu": {"gpu_name": "CPU Only", "gpu_cores": None, "memory_bandwidth_gbs": None,
                       "vram_total_gb": None, "vram_available_gb": None, "compute_capability": None,
                       "cuda_version": None, "mps_supported": False, "unified_memory": False},
                "accelerator": {"neural_engine_tops": None, "architecture": None},
                "storage": {"total_gb": None, "available_gb": None, "usage_percentage": None},
                "backend_type": "cpu",
                "timestamp": time.time(),
            }

    @classmethod
    def warm_up_accelerator(cls, duration_seconds: float = 1.0) -> bool:
        """Warm up CPU with compute workload.
        
        Runs lightweight computation loop to bring CPU to stable performance
        state. Less critical than GPU warm-up but still useful for consistent
        benchmarking results.
        
        Args:
            duration_seconds: How long to run warm-up operations (default: 1.0).
            
        Returns:
            bool: True if warm-up completed successfully, False otherwise.
            
        Note:
            CPU warm-up is minimal compared to GPU since CPUs don't have
            dynamic clock management like modern GPUs.
        """
        try:
            logger.info(f"Warming up CPU for {duration_seconds}s...")
            t0 = time.time()
            
            # Run bounded compute loop
            n = 0
            iterations = 0
            while time.time() - t0 < max(0.05, float(duration_seconds)):
                # Lightweight integer arithmetic to engage CPU
                for _ in range(10000):
                    n += (_ * 7) % 13
                iterations += 1
                
                # Small sleep to prevent complete CPU saturation
                if iterations % 10 == 0:
                    time.sleep(0.001)
            
            logger.info(f"CPU warm-up completed successfully ({iterations} iterations)")
            return True
            
        except Exception as e:
            logger.warning(f"CPU warm-up failed: {e}")
            return False

    @classmethod
    def get_performance_evaluation(cls) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics for CPU-only backend.
        
        Evaluates hardware capabilities and returns performance scores for
        inference and fine-tuning workloads. Scoring acknowledges CPU limitations
        compared to GPU-accelerated backends.
        
        Scoring methodology:
            - Inference: CPU cores (40%), memory capacity (30%), memory bandwidth est. (20%), disk (10%)
            - Fine-tuning: Memory capacity (50%), CPU cores (30%), disk (15%), memory bandwidth (5%)
        
        Normalization:
            - CPU cores: 64 cores = 100 points
            - Memory: 128GB = 100 points
            - Memory bandwidth: Estimated from CPU specs, 100GB/s = 100 points
            - Disk: 500GB available = 100 points
        
        Returns:
            Dict containing performance metrics and scores (0-100 scale):
            {
                "backend_type": "cpu",
                "cpu_model": str,
                "total_memory_gb": float,
                "available_memory_gb": float,
                "compute_units": int,  # CPU cores
                "cpu_performance_units": int,
                "global_inference_score": float,
                "global_inference_label": str,
                "global_finetuning_score": float,
                "global_finetuning_label": str,
                "cpu_score": float,
                "memory_score": float,
                "performance_breakdown": PerformanceBreakdown,
                ...
            }
            
        Note:
            CPU backend scores are generally lower than GPU backends due to
            lack of parallel processing capabilities. Scores are calibrated
            to be realistic about CPU limitations while still differentiating
            between high-end and low-end CPU systems.
        """
        try:
            # Import optional dependencies
            try:
                import psutil
                import cpuinfo
            except ImportError as e:
                logger.warning(f"Optional hardware detection dependency missing: {e}")
                psutil = None
                cpuinfo = None
            
            # Get hardware info
            hw_info = cls.get_hardware_info()
            
            # Extract key metrics
            total_cores = hw_info["cpu"]["total_cores"] or 1
            total_memory_gb = hw_info["memory"]["total_memory_gb"] or 0
            available_memory_gb = hw_info["memory"]["available_memory_gb"] or 0
            disk_available_gb = hw_info["storage"]["available_gb"] or 0
            cpu_model = hw_info["cpu"]["model"]
            
            # === SCORING WEIGHTS ===
            # Inference: CPU (40%), Memory Capacity (30%), Memory BW (20%), Disk (10%)
            INF_WEIGHTS = {"cpu": 0.40, "memory_capacity": 0.30, "memory_bandwidth": 0.20, "disk": 0.10}
            
            # Fine-tuning: Memory Capacity (50%), CPU (30%), Disk (15%), Memory BW (5%)
            FT_WEIGHTS = {"memory_capacity": 0.50, "cpu": 0.30, "disk": 0.15, "memory_bandwidth": 0.05}
            
            # === NORMALIZATION FACTORS ===
            NORM_CPU_CORES = 64.0      # 64 cores = 100 points
            NORM_MEMORY_GB = 128.0     # 128GB RAM = 100 points
            NORM_MEM_BW_GBS = 100.0    # 100GB/s = 100 points (estimated)
            NORM_DISK_GB = 500.0       # 500GB available = 100 points
            
            # === COMPONENT SCORES (0-100 scale) ===
            
            # CPU Score: Based on core count
            cpu_score = min(100.0, (total_cores / NORM_CPU_CORES) * 100.0)
            
            # Memory Score: Based on total memory capacity
            memory_capacity_score = min(100.0, (total_memory_gb / NORM_MEMORY_GB) * 100.0)
            
            # Memory Bandwidth Score: Estimate based on CPU architecture
            # Modern CPUs: ~50-100 GB/s, older CPUs: ~20-40 GB/s
            estimated_mem_bw = total_cores * 1.5  # Rough heuristic: 1.5 GB/s per core
            memory_bandwidth_score = min(100.0, (estimated_mem_bw / NORM_MEM_BW_GBS) * 100.0)
            
            # Disk Score: Based on available storage
            disk_score = min(100.0, (disk_available_gb / NORM_DISK_GB) * 100.0)
            
            # === GLOBAL SCORES ===
            
            # Inference Score
            inference_score = (
                cpu_score * INF_WEIGHTS["cpu"] +
                memory_capacity_score * INF_WEIGHTS["memory_capacity"] +
                memory_bandwidth_score * INF_WEIGHTS["memory_bandwidth"] +
                disk_score * INF_WEIGHTS["disk"]
            )
            
            # Fine-tuning Score
            finetuning_score = (
                memory_capacity_score * FT_WEIGHTS["memory_capacity"] +
                cpu_score * FT_WEIGHTS["cpu"] +
                disk_score * FT_WEIGHTS["disk"] +
                memory_bandwidth_score * FT_WEIGHTS["memory_bandwidth"]
            )
            
            # Round scores
            inference_score = round(inference_score, 2)
            finetuning_score = round(finetuning_score, 2)
            
            # === LABELS ===
            def score_to_label(score: float) -> str:
                """Convert 0-100 score to qualitative label."""
                if score >= 85: return "Amazing"
                elif score >= 70: return "Excellent"
                elif score >= 55: return "Very Good"
                elif score >= 40: return "Good"
                elif score >= 25: return "Medium"
                elif score >= 10: return "Poor"
                else: return "Terrible"
            
            inference_label = score_to_label(inference_score)
            finetuning_label = score_to_label(finetuning_score)
            
            # === BUILD RESULT ===
            result = {
                "backend_type": "cpu",
                "gpu_name": "CPU Only",
                "cpu_model": cpu_model,
                "total_memory_gb": total_memory_gb,
                "available_memory_gb": available_memory_gb,
                "memory_bandwidth_gbs": round(estimated_mem_bw, 2),
                "disk_total_gb": hw_info["storage"]["total_gb"],
                "disk_available_gb": disk_available_gb,
                "estimated_tflops": None,  # Not applicable for CPUs
                "cpu_performance_units": total_cores,
                "neural_engine_tops": None,
                "cuda_version": None,
                "compute_capability": None,
                "architecture": hw_info["cpu"]["architecture"],
                "global_inference_score": inference_score,
                "global_inference_label": inference_label,
                "global_finetuning_score": finetuning_score,
                "global_finetuning_label": finetuning_label,
                "gpu_score": 0.0,  # No GPU
                "cpu_score": round(cpu_score, 2),
                "memory_score": round(memory_capacity_score, 2),
                "unified_memory": False,
                "system_platform": hw_info["system"]["platform"],
                "performance_breakdown": {
                    "compute_score": round(cpu_score, 2),
                    "memory_bandwidth_score": round(memory_bandwidth_score, 2),
                    "memory_capacity_score": round(memory_capacity_score, 2),
                    "cpu_performance_score": round(cpu_score, 2),
                    "disk_score": round(disk_score, 2),
                },
            }
            
            logger.info(
                f"CPU performance evaluated: Inference={inference_score:.1f} ({inference_label}), "
                f"Fine-tuning={finetuning_score:.1f} ({finetuning_label})"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"CPU performance evaluation failed: {e}")
            # Return minimal fallback
            cores = os.cpu_count() or 1
            base_score = min(100.0, cores * 5.0)  # 5 points per core
            return {
                "backend_type": "cpu",
                "gpu_name": "CPU Only",
                "cpu_model": platform.processor() or "Unknown CPU",
                "total_memory_gb": None,
                "available_memory_gb": None,
                "memory_bandwidth_gbs": None,
                "disk_total_gb": None,
                "disk_available_gb": None,
                "estimated_tflops": None,
                "cpu_performance_units": cores,
                "neural_engine_tops": None,
                "cuda_version": None,
                "compute_capability": None,
                "architecture": platform.machine(),
                "global_inference_score": round(base_score, 2),
                "global_inference_label": "Poor",
                "global_finetuning_score": round(base_score * 0.8, 2),
                "global_finetuning_label": "Poor",
                "gpu_score": 0.0,
                "cpu_score": round(base_score, 2),
                "memory_score": 0.0,
                "unified_memory": False,
                "system_platform": platform.system(),
                "performance_breakdown": {
                    "compute_score": round(base_score, 2),
                    "memory_bandwidth_score": 0.0,
                    "memory_capacity_score": 0.0,
                    "cpu_performance_score": round(base_score, 2),
                    "disk_score": 0.0,
                },
            }
    
    @classmethod
    def get_flat_hardware_data(cls) -> Dict[str, Any]:
        """Get hardware data in flat format compatible with HardwareProfile entity.
        
        Returns hardware specifications as a flat dictionary ready for database
        insertion. For CPU backend, get_performance_evaluation() already returns
        data in the correct flat format.
        
        Returns:
            Flat dict with all fields matching HardwareProfile columns.
            
        Raises:
            HardwareException: If hardware data collection fails.
        """
        # get_performance_evaluation() already returns flat structure
        return cls.get_performance_evaluation()
