"""CUDA engine for NVIDIA GPU inference.

This module implements the CUDA backend for local LLM inference on systems
with NVIDIA GPUs. It provides:
- Hardware detection via PyTorch CUDA and NVML
- Performance evaluation for inference and fine-tuning
- GPU warm-up for optimal benchmarking
- Cross-platform support (Windows and Linux)

Architecture:
    CUDA Engine → PyTorch CUDA + NVML
    ┌───────────────────────────────────────────────────────────┐
    │ get_hardware_info()                                       │
    │  └─> Detect GPU, VRAM, compute capability via NVML       │
    └───────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────────────┐
    │ get_performance_evaluation()                              │
    │  1. Calculate TFLOPS (FP32, FP16, BF16)                   │
    │  2. Measure memory bandwidth                              │
    │  3. Score inference & fine-tuning performance             │
    └───────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────────────┐
    │ warm_up_accelerator()                                     │
    │  └─> Matrix operations to boost GPU clocks               │
    └───────────────────────────────────────────────────────────┘

Hardware Detection:
    - CUDA availability: torch.cuda.is_available()
    - GPU information: NVML (pynvml library)
    - Best GPU selection: highest VRAM capacity
    - OS-agnostic: Works on Windows and Linux

Performance Scoring:
    Inference weights:
        - GPU compute (40%): Tensor TFLOPS (BF16/FP16)
        - Memory bandwidth (30%): GB/s throughput
        - VRAM capacity (15%): GPU memory size
        - CPU performance (5%): Multi-core GHz
        - System RAM (5%): Host memory
        - PCIe bandwidth (5%): Bus capacity
    
    Fine-tuning weights:
        - VRAM capacity (45%): Critical for batch size
        - GPU compute (35%): Training throughput
        - Memory bandwidth (10%): Data transfer speed
        - System RAM (5%): Host memory
        - PCIe bandwidth (5%): Bus capacity

Example:
    Get CUDA hardware information::

        from src.engines.cuda_engine import CUDA_Engine

        # Detect hardware
        hw_info = CUDA_Engine.get_hardware_info()
        print(f"GPU: {hw_info['gpu']['gpu_name']}")
        print(f"VRAM: {hw_info['gpu']['vram_total_gb']} GB")

        # Warm up GPU
        CUDA_Engine.warm_up_accelerator(1.5)

        # Evaluate performance
        perf = CUDA_Engine.get_performance_evaluation()
        print(f"Inference score: {perf['global_inference_score']}/100")
        print(f"Label: {perf['global_inference_label']}")

Note:
    - Requires torch with CUDA support
    - Requires pynvml for GPU monitoring
    - All methods return fallback values if CUDA unavailable
    - Thread-safe through BaseEngine._lock

Warning:
    Model loading and generation methods not yet implemented.
    Only hardware detection methods are functional.
"""

import os
import re
import time
import platform
from typing import Any, Optional, Tuple, Generator, Dict, Union
from pathlib import Path

from src.engines.base_engine import BaseEngine
from src.core.logging import logger
from src.core.exceptions import (
    HardwareException,
    EngineException,
)


class CUDA_Engine(BaseEngine):
    """Engine for NVIDIA CUDA GPU inference.
    
    Provides hardware detection and performance evaluation for NVIDIA GPUs
    using PyTorch CUDA backend and NVML monitoring library.
    
    Hardware Specs Reference Tables:
        CUDA_PER_SM: CUDA cores and Tensor cores per SM by compute capability
        TC_OPS: Tensor core operations per precision by compute capability
    
    Note:
        LLM inference methods (load, generate) not yet implemented.
        Use for hardware detection only.
    """

    # NVIDIA GPU architecture specifications
    # Maps compute capability major version to (CUDA cores/SM, Tensor cores/SM)
    _CUDA_PER_SM = {
        7: (64, 8),    # Turing (SM 7.5): RTX 20xx, Quadro RTX
        8: (128, 4),   # Ampere (SM 8.x): RTX 30xx, A100
        9: (128, 4),   # Ada Lovelace / Hopper (SM 9.x): RTX 40xx, H100
    }

    # Tensor core operations per clock per precision
    # Format: precision → (ops_per_TC_per_clock, minimum_compute_capability)
    _TC_OPS = {
        "fp16": (256 * 2, 7),  # 256 FMA = 512 FLOP, requires CC 7.0+
        "bf16": (256 * 2, 8),  # 256 FMA = 512 FLOP, requires CC 8.0+
    }

    # Performance scoring weights for inference workload (sum = 1.0)
    _WEIGHTS_INFERENCE = {
        "gpu_compute": 0.40,   # Tensor TFLOPS (BF16/FP16)
        "gpu_bw": 0.30,        # Memory bandwidth GB/s
        "gpu_vram": 0.15,      # VRAM capacity
        "cpu_single": 0.05,    # CPU performance units
        "sys_ram": 0.05,       # System RAM
        "pcie": 0.05,          # PCIe bus capacity
    }

    # Normalization factors for inference scoring
    _NORM_INFERENCE = {
        "tflops": 80,          # 80 TFLOPS FP16 reference
        "bandwidth": 500,      # 500 GB/s (7B models saturate beyond this)
        "vram": 12,            # 12 GB (sufficient for 7B INT4)
        "cpu_ghz": 3.6,        # 3.6 GHz single-core reference
        "ram": 24,             # 24 GB (comfortable for multi-tasking)
        "pcie": 32,            # Gen3 x16 or Gen4 x8
    }

    # Performance scoring weights for fine-tuning workload (sum = 1.0)
    _FINETUNE_WEIGHTS = {
        "gpu_compute": 0.35,
        "gpu_vram": 0.45,      # Critical for batch size
        "gpu_bw": 0.10,
        "sys_ram": 0.05,
        "pcie": 0.05,
    }

    # Normalization factors for fine-tuning scoring
    _FINETUNE_NORM = {
        "tflops": 600,         # High-end training GPU reference
        "vram": 96,            # 2x48 GB (dual GPU training)
        "bandwidth": 1200,     # 1.2 TB/s (H100 reference)
        "ram": 64,             # 64 GB host memory
        "pcie": 32,            # Gen3 x16
    }

    @classmethod
    def quant_and_save_from_hf_format(
        cls,
        local_hf_path: Union[str, Path],
        local_dest_path: Union[str, Path],
        quantize: bool = True,
        q_bits: str = "4",
        *args
    ) -> None:
        """Convert and quantize HuggingFace model to CUDA-compatible format.
        
        NOT YET IMPLEMENTED.
        
        Args:
            local_hf_path: Path to HuggingFace model directory.
            local_dest_path: Destination directory for converted model.
            quantize: Whether to apply quantization.
            q_bits: Quantization bits ("4" or "8").
            *args: Additional arguments.
        
        Raises:
            NotImplementedError: Always raised (method not implemented).
        """
        raise NotImplementedError("CUDA model quantization not yet implemented")

    @classmethod
    def get_model_and_tokenizer(
        cls,
        llm_id: str,
        llm_local_path: Union[str, Path],
        *args
    ) -> Tuple[Any, Any]:
        """Load or retrieve cached model and tokenizer for CUDA inference.
        
        NOT YET IMPLEMENTED.
        
        Args:
            llm_id: Unique identifier for the model.
            llm_local_path: Path to the model directory.
            *args: Additional arguments.
        
        Returns:
            Tuple of (model, tokenizer).
        
        Raises:
            NotImplementedError: Always raised (method not implemented).
        """
        raise NotImplementedError("CUDA model loading not yet implemented")

    @classmethod
    def generate_stream(
        cls,
        model: Any,
        tokenizer: Any,
        prompt: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs
    ) -> Generator[str, None, None]:
        """Generate text tokens in streaming fashion via CUDA.
        
        NOT YET IMPLEMENTED.
        
        Args:
            model: Loaded model instance.
            tokenizer: Loaded tokenizer instance.
            prompt: Chat-style messages.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            top_p: Nucleus sampling threshold.
            **kwargs: Additional generation parameters.
        
        Yields:
            String tokens.
        
        Raises:
            NotImplementedError: Always raised (method not implemented).
        """
        raise NotImplementedError("CUDA generation not yet implemented")
        yield  # Make it a generator

    # ======================= HARDWARE DETECTION =======================

    @classmethod
    def _cuda_available(cls) -> bool:
        """Check if CUDA is available via PyTorch.
        
        Returns:
            bool: True if CUDA runtime available and at least one GPU detected.
        
        Note:
            Uses torch.cuda.is_available() which checks both CUDA installation
            and GPU presence.
        """
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            logger.warning("PyTorch not installed, CUDA unavailable")
            return False
        except Exception as e:
            logger.warning(f"CUDA availability check failed: {e}")
            return False

    @classmethod
    def _init_nvml(cls) -> bool:
        """Initialize NVIDIA Management Library (NVML).
        
        Returns:
            bool: True if NVML initialized successfully, False otherwise.
        
        Note:
            Safe to call multiple times. Returns True if already initialized.
        """
        try:
            import pynvml as nv
            try:
                nv.nvmlInit()
                return True
            except nv.NVMLError as e:
                # Already initialized is not an error
                if "Already initialized" in str(e) or "Initialized" in str(e):
                    return True
                logger.warning(f"NVML initialization failed: {e}")
                return False
        except ImportError:
            logger.warning("pynvml not installed, GPU monitoring unavailable")
            return False

    @classmethod
    def _get_nvml_gpus(cls) -> list[dict]:
        """Get list of GPUs detected by NVML.
        
        Returns:
            List of dictionaries describing each GPU:
            [
                {
                    "id": int,
                    "handle": nvmlDevice,
                    "name": str,
                    "vram_total_mb": float,
                    "vram_free_mb": float
                },
                ...
            ]
            Empty list if NVML unavailable or no GPUs found.
        
        Note:
            Automatically initializes NVML if needed.
        """
        if not cls._init_nvml():
            return []
        
        try:
            import pynvml as nv
            
            gpus = []
            device_count = nv.nvmlDeviceGetCount()
            
            for idx in range(device_count):
                try:
                    handle = nv.nvmlDeviceGetHandleByIndex(idx)
                    name = nv.nvmlDeviceGetName(handle)
                    mem_info = nv.nvmlDeviceGetMemoryInfo(handle)
                    
                    gpus.append({
                        "id": idx,
                        "handle": handle,
                        "name": name,
                        "vram_total_mb": mem_info.total / (1024 ** 2),
                        "vram_free_mb": mem_info.free / (1024 ** 2),
                    })
                except nv.NVMLError as e:
                    logger.warning(f"Failed to get info for GPU {idx}: {e}")
                    continue
            
            return gpus
            
        except Exception as e:
            logger.error(f"Failed to enumerate GPUs: {e}")
            return []

    @classmethod
    def _select_best_gpu(cls, gpus: list[dict]) -> Optional[dict]:
        """Select best GPU based on total VRAM capacity.
        
        Args:
            gpus: List of GPU dictionaries from _get_nvml_gpus().
        
        Returns:
            GPU dictionary with highest VRAM, or None if list empty.
        """
        if not gpus:
            return None
        return max(gpus, key=lambda g: g["vram_total_mb"])

    @classmethod
    def _get_cpu_performance_units(cls) -> float:
        """Calculate CPU performance units (cores × GHz).
        
        Returns:
            float: Performance units (physical_cores * max_frequency_ghz).
                  Fallback: 10.0 if detection fails.
        
        Note:
            Uses psutil for cross-platform CPU detection.
        """
        try:
            import psutil
            
            freq = psutil.cpu_freq()
            max_freq_mhz = freq.max if freq and freq.max else (freq.current if freq else 2500)
            physical_cores = psutil.cpu_count(logical=False) or 4
            
            return (physical_cores * max_freq_mhz / 1000)  # Convert MHz to GHz
            
        except Exception as e:
            logger.warning(f"CPU performance detection failed: {e}")
            return 10.0  # Fallback

    @classmethod
    def _get_pcie_capacity(cls, handle) -> float:
        """Calculate PCIe bus capacity units (generation × width).
        
        Args:
            handle: NVML device handle.
        
        Returns:
            float: PCIe capacity (gen * width). E.g., Gen3 x16 = 48.
                  Fallback: 16.0 if detection fails.
        
        Note:
            Higher values indicate better host-device bandwidth.
        """
        try:
            import pynvml as nv
            
            gen = nv.nvmlDeviceGetMaxPcieLinkGeneration(handle)
            width = nv.nvmlDeviceGetMaxPcieLinkWidth(handle)
            
            return float(gen * width)
            
        except Exception as e:
            logger.warning(f"PCIe capacity detection failed: {e}")
            return 16.0  # Fallback (Gen3 x16 / Gen4 x8)

    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        """Get comprehensive hardware information for NVIDIA CUDA backend.
        
        Returns detailed hardware specifications including GPU model, VRAM,
        compute capability, system resources, and CUDA availability.
        
        Returns:
            Dict containing hardware specifications:
            {
                "system": {
                    "platform": str,
                    "platform_version": str,
                    "machine": str,
                    "processor": str
                },
                "cpu": {
                    "model": str,
                    "architecture": str,
                    "total_cores": int,
                    "logical_cores": int
                },
                "memory": {
                    "total_memory_gb": float,
                    "available_memory_gb": float,
                    "memory_pressure": float,
                    "memory_type": "system"
                },
                "gpu": {
                    "gpu_name": str,
                    "gpu_index": int,
                    "cuda_cores": int,
                    "vram_total_gb": float,
                    "vram_available_gb": float,
                    "compute_capability": str,
                    "memory_bandwidth_gbs": float,
                    "cuda_available": bool,
                    "unified_memory": False
                },
                "storage": {
                    "total_gb": float,
                    "available_gb": float,
                    "usage_percentage": float
                },
                "backend_type": "cuda",
                "timestamp": float
            }
        
        Raises:
            HardwareException: If critical hardware detection fails.
        
        Note:
            Returns fallback values if CUDA unavailable rather than raising.
            Safe to call even on systems without NVIDIA GPUs.
        
        Examples:
            >>> hw_info = CUDA_Engine.get_hardware_info()
            >>> print(f"GPU: {hw_info['gpu']['gpu_name']}")
            >>> print(f"VRAM: {hw_info['gpu']['vram_total_gb']} GB")
            >>> print(f"Compute: {hw_info['gpu']['compute_capability']}")
        """
        try:
            # Import required modules
            try:
                import psutil
                import cpuinfo
                import torch
            except ImportError as e:
                logger.error(f"Required hardware detection dependency missing: {e}")
                raise HardwareException(
                    f"Missing dependency for hardware detection: {e}",
                    trace=str(e)
                )
            
            # Check CUDA availability
            cuda_available = cls._cuda_available()
            
            # Get system info
            vm = psutil.virtual_memory()
            total_memory_gb = vm.total / (1024 ** 3)
            available_memory_gb = vm.available / (1024 ** 3)
            memory_pressure = 1.0 - (vm.available / vm.total)
            
            disk = psutil.disk_usage('/')
            disk_total_gb = disk.total / (1024 ** 3)
            disk_available_gb = disk.free / (1024 ** 3)
            disk_usage_pct = disk.percent
            
            cpu_info_data = cpuinfo.get_cpu_info()
            cpu_model = cpu_info_data.get("brand_raw", "Unknown CPU")
            total_cores = psutil.cpu_count(logical=False) or 4
            logical_cores = psutil.cpu_count(logical=True) or 8
            
            # GPU information (if available)
            gpu_info = {
                "gpu_name": "No NVIDIA GPU",
                "gpu_index": -1,
                "cuda_cores": 0,
                "vram_total_gb": 0.0,
                "vram_available_gb": 0.0,
                "compute_capability": "N/A",
                "memory_bandwidth_gbs": 0.0,
                "cuda_available": cuda_available,
                "unified_memory": False
            }
            
            if cuda_available:
                gpus = cls._get_nvml_gpus()
                if gpus:
                    best_gpu = cls._select_best_gpu(gpus)
                    if best_gpu:
                        # Get basic GPU info
                        gpu_info["gpu_name"] = best_gpu["name"]
                        gpu_info["gpu_index"] = best_gpu["id"]
                        gpu_info["vram_total_gb"] = best_gpu["vram_total_mb"] / 1024
                        gpu_info["vram_available_gb"] = best_gpu["vram_free_mb"] / 1024
                        
                        # Get compute capability and CUDA cores
                        device_id = best_gpu["id"]
                        props = torch.cuda.get_device_properties(device_id)
                        compute_cap = f"{props.major}.{props.minor}"
                        gpu_info["compute_capability"] = compute_cap
                        
                        cores_per_sm, _ = cls._CUDA_PER_SM.get(props.major, (64, 0))
                        total_cuda_cores = props.multi_processor_count * cores_per_sm
                        gpu_info["cuda_cores"] = total_cuda_cores
                        
                        # Get memory bandwidth (requires NVML)
                        try:
                            import pynvml as nv
                            handle = best_gpu["handle"]
                            mem_clock_mhz = nv.nvmlDeviceGetClockInfo(handle, nv.NVML_CLOCK_MEM)
                            bus_bits = nv.nvmlDeviceGetMemoryBusWidth(handle)
                            # Bandwidth = 2 * clock * bus_width / 8 (DDR, convert bits to bytes)
                            bandwidth_gbs = 2 * mem_clock_mhz / 1000 * bus_bits / 8
                            gpu_info["memory_bandwidth_gbs"] = round(bandwidth_gbs, 1)
                        except Exception as e:
                            logger.warning(f"Could not get memory bandwidth: {e}")
            
            # Build complete hardware info
            hardware_info = {
                "system": {
                    "platform": platform.system(),
                    "platform_version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor() or cpu_model
                },
                "cpu": {
                    "model": cpu_model,
                    "architecture": platform.machine(),
                    "total_cores": total_cores,
                    "logical_cores": logical_cores
                },
                "memory": {
                    "total_memory_gb": round(total_memory_gb, 2),
                    "available_memory_gb": round(available_memory_gb, 2),
                    "memory_pressure": round(memory_pressure, 3),
                    "memory_type": "system"
                },
                "gpu": gpu_info,
                "storage": {
                    "total_gb": round(disk_total_gb, 2),
                    "available_gb": round(disk_available_gb, 2),
                    "usage_percentage": round(disk_usage_pct, 2)
                },
                "backend_type": "cuda",
                "timestamp": time.time()
            }
            
            logger.info(
                f"CUDA hardware detected: {gpu_info['gpu_name']}, "
                f"{gpu_info['cuda_cores']} CUDA cores, "
                f"{gpu_info['vram_total_gb']:.1f}GB VRAM"
            )
            
            return hardware_info
            
        except Exception as e:
            logger.exception(f"CUDA hardware detection failed: {e}")
            raise HardwareException(
                "Failed to detect CUDA hardware",
                trace=str(e)
            )

    @classmethod
    def warm_up_accelerator(cls, duration_seconds: float = 1.0) -> bool:
        """Warm up NVIDIA GPU to boost clock speeds for benchmarking.
        
        Runs matrix multiplication operations on GPU to bring it to optimal
        performance state before measurements. Important for GPUs with
        dynamic clock management.
        
        Args:
            duration_seconds: How long to run warm-up operations (default: 1.0).
        
        Returns:
            bool: True if warm-up completed successfully, False otherwise.
        
        Note:
            Silently returns False if CUDA unavailable rather than raising.
            Uses 4096x4096 matrix multiplications on primary GPU.
        
        Examples:
            >>> success = CUDA_Engine.warm_up_accelerator(1.5)
            >>> if success:
            ...     print("GPU ready for benchmarking")
        """
        if not cls._cuda_available():
            logger.warning("CUDA not available, skipping GPU warm-up")
            return False
        
        try:
            import torch
            
            # Get best GPU
            gpus = cls._get_nvml_gpus()
            if not gpus:
                logger.warning("No GPUs detected, skipping warm-up")
                return False
            
            best_gpu = cls._select_best_gpu(gpus)
            device_id = best_gpu["id"]
            
            logger.info(f"Warming up GPU {device_id} ({best_gpu['name']}) for {duration_seconds}s...")
            
            torch.cuda.set_device(device_id)
            start_time = time.time()
            
            # Run matrix operations to boost clocks
            size = 4096
            while (time.time() - start_time) < duration_seconds:
                a = torch.randn(size, size, device="cuda")
                b = torch.randn(size, size, device="cuda")
                c = torch.matmul(a, b)
                del a, b, c
            
            torch.cuda.synchronize()
            logger.info("GPU warm-up completed successfully")
            return True
            
        except Exception as e:
            logger.exception(f"GPU warm-up failed: {e}")
            return False

    @classmethod
    def get_performance_evaluation(cls) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics for NVIDIA CUDA backend.
        
        Evaluates hardware capabilities and returns normalized performance scores
        for inference and fine-tuning workloads. Scoring based on TFLOPS, memory
        bandwidth, VRAM capacity, and system resources.
        
        Scoring methodology:
            Inference (0-100 scale):
                - GPU compute (40%): Tensor TFLOPS (BF16/FP16)
                - Memory bandwidth (30%): GB/s throughput
                - VRAM capacity (15%): GPU memory size
                - CPU performance (5%): Multi-core units
                - System RAM (5%): Host memory
                - PCIe capacity (5%): Bus bandwidth
            
            Fine-tuning (0-100 scale):
                - VRAM capacity (45%): Critical for batch size
                - GPU compute (35%): Training throughput
                - Memory bandwidth (10%): Data transfer
                - System RAM (5%): Host memory
                - PCIe capacity (5%): Bus bandwidth
        
        Returns:
            Dict containing performance metrics and scores:
            {
                "backend_type": "cuda",
                "gpu_name": str,
                "cpu_model": str,
                "total_memory_gb": float,
                "available_memory_gb": float,
                "memory_bandwidth_gbs": float,
                "disk_total_gb": float,
                "disk_available_gb": float,
                "estimated_tflops": float,
                "compute_units": int,
                "cpu_performance_units": float,
                "cuda_version": str,
                "compute_capability": str,
                "architecture": str,
                "global_inference_score": float,
                "global_inference_label": str,
                "global_finetuning_score": float,
                "global_finetuning_label": str,
                "gpu_score": float,
                "cpu_score": float,
                "memory_score": float,
                "unified_memory": False,
                "accelerator_available": bool,
                "system_platform": str,
                "performance_breakdown": dict
            }
        
        Raises:
            HardwareException: If evaluation fails critically.
        
        Note:
            Returns fallback scores if CUDA unavailable.
            Should call warm_up_accelerator() before evaluation for accuracy.
        
        Examples:
            >>> CUDA_Engine.warm_up_accelerator(1.5)
            >>> eval_result = CUDA_Engine.get_performance_evaluation()
            >>> print(f"Inference: {eval_result['global_inference_score']}/100")
            >>> print(f"Label: {eval_result['global_inference_label']}")
            >>> print(f"Fine-tuning: {eval_result['global_finetuning_score']}/100")
        """
        try:
            import torch
            import psutil
            
            # Get base hardware info
            hw_info = cls.get_hardware_info()
            
            cuda_available = hw_info["gpu"]["cuda_available"]
            
            # Initialize scores with fallback values
            gpu_score = 0.0
            mem_bandwidth_score = 0.0
            vram_score = 0.0
            estimated_tflops = 0.0
            cuda_version = "N/A"
            architecture = "N/A"
            tensor_tflops = {}
            sm_clock_ghz = 0.0
            
            if cuda_available:
                gpus = cls._get_nvml_gpus()
                if gpus:
                    best_gpu = cls._select_best_gpu(gpus)
                    device_id = best_gpu["id"]
                    handle = best_gpu["handle"]
                    
                    # Get GPU clocks and specs
                    try:
                        import pynvml as nv
                        sm_clock_mhz = nv.nvmlDeviceGetClockInfo(handle, nv.NVML_CLOCK_SM)
                        sm_clock_ghz = sm_clock_mhz / 1000
                        mem_clock_mhz = nv.nvmlDeviceGetClockInfo(handle, nv.NVML_CLOCK_MEM)
                        bus_bits = nv.nvmlDeviceGetMemoryBusWidth(handle)
                        bandwidth_gbs = 2 * mem_clock_mhz / 1000 * bus_bits / 8
                    except Exception as e:
                        logger.warning(f"Failed to get GPU clocks: {e}")
                        sm_clock_ghz = 1.5  # Fallback
                        bandwidth_gbs = hw_info["gpu"]["memory_bandwidth_gbs"]
                    
                    # Get PyTorch device properties
                    props = torch.cuda.get_device_properties(device_id)
                    sm_count = props.multi_processor_count
                    compute_cap_major = props.major
                    
                    # Calculate CUDA cores and tensor cores
                    cores_per_sm, tc_per_sm = cls._CUDA_PER_SM.get(compute_cap_major, (64, 0))
                    total_cuda_cores = sm_count * cores_per_sm
                    
                    # Calculate FP32 TFLOPS
                    # 2 ops per CUDA core per clock (FMA = mul + add)
                    fp32_tflops = 2 * sm_count * cores_per_sm * sm_clock_ghz / 1000
                    
                    # Calculate Tensor TFLOPS (FP16, BF16)
                    for precision, (ops_per_tc, min_cc) in cls._TC_OPS.items():
                        if compute_cap_major >= min_cc:
                            tflops = (sm_count * tc_per_sm * ops_per_tc * sm_clock_ghz) / 1000
                            tensor_tflops[precision] = round(tflops, 2)
                        else:
                            tensor_tflops[precision] = 0.0
                    
                    # Use best tensor performance for scoring
                    estimated_tflops = tensor_tflops.get("bf16", tensor_tflops.get("fp16", fp32_tflops))
                    
                    # Get CUDA version
                    try:
                        cuda_version = torch.version.cuda or "Unknown"
                    except:
                        cuda_version = "Unknown"
                    
                    # Determine architecture
                    if compute_cap_major == 7:
                        architecture = "Turing"
                    elif compute_cap_major == 8:
                        architecture = "Ampere"
                    elif compute_cap_major == 9:
                        architecture = "Ada Lovelace / Hopper"
                    else:
                        architecture = f"Compute {props.major}.{props.minor}"
                    
                    # Calculate component scores
                    vram_gb = hw_info["gpu"]["vram_total_gb"]
                    vram_score = min(100, (vram_gb / cls._NORM_INFERENCE["vram"]) * 100)
                    mem_bandwidth_score = min(100, (bandwidth_gbs / cls._NORM_INFERENCE["bandwidth"]) * 100)
                    gpu_score = min(100, (estimated_tflops / cls._NORM_INFERENCE["tflops"]) * 100)
            
            # CPU and system scores
            cpu_perf_units = cls._get_cpu_performance_units()
            cpu_score = min(100, (cpu_perf_units / (cls._NORM_INFERENCE["cpu_ghz"] * 12)) * 100)
            
            sys_ram_gb = hw_info["memory"]["total_memory_gb"]
            ram_score = min(100, (sys_ram_gb / cls._NORM_INFERENCE["ram"]) * 100)
            
            # PCIe score
            pcie_score = 50.0  # Default fallback
            if cuda_available and gpus:
                pcie_units = cls._get_pcie_capacity(handle)
                pcie_score = min(100, (pcie_units / cls._NORM_INFERENCE["pcie"]) * 100)
            
            # Calculate weighted inference score
            inference_score = (
                cls._WEIGHTS_INFERENCE["gpu_compute"] * gpu_score +
                cls._WEIGHTS_INFERENCE["gpu_bw"] * mem_bandwidth_score +
                cls._WEIGHTS_INFERENCE["gpu_vram"] * vram_score +
                cls._WEIGHTS_INFERENCE["cpu_single"] * cpu_score +
                cls._WEIGHTS_INFERENCE["sys_ram"] * ram_score +
                cls._WEIGHTS_INFERENCE["pcie"] * pcie_score
            )
            
            # Calculate weighted fine-tuning score (normalized to different factors)
            vram_score_ft = min(100, (vram_gb / cls._FINETUNE_NORM["vram"]) * 100) if cuda_available else 0
            gpu_score_ft = min(100, (estimated_tflops / cls._FINETUNE_NORM["tflops"]) * 100)
            bw_score_ft = min(100, (bandwidth_gbs / cls._FINETUNE_NORM["bandwidth"]) * 100) if cuda_available else 0
            ram_score_ft = min(100, (sys_ram_gb / cls._FINETUNE_NORM["ram"]) * 100)
            
            finetuning_score = (
                cls._FINETUNE_WEIGHTS["gpu_compute"] * gpu_score_ft +
                cls._FINETUNE_WEIGHTS["gpu_vram"] * vram_score_ft +
                cls._FINETUNE_WEIGHTS["gpu_bw"] * bw_score_ft +
                cls._FINETUNE_WEIGHTS["sys_ram"] * ram_score_ft +
                cls._FINETUNE_WEIGHTS["pcie"] * pcie_score
            )
            
            # Generate labels
            def get_label(score: float) -> str:
                if score >= 90: return "Amazing"
                elif score >= 80: return "Excellent"
                elif score >= 70: return "Very High"
                elif score >= 60: return "High"
                elif score >= 50: return "Good"
                elif score >= 40: return "Medium"
                elif score >= 30: return "Bad"
                elif score >= 20: return "Very Bad"
                elif score >= 10: return "Poor"
                else: return "Terrible"
            
            inference_label = get_label(inference_score)
            finetuning_label = get_label(finetuning_score)
            
            # Build performance breakdown
            performance_breakdown = {
                "gpu_compute_score": round(gpu_score, 2),
                "memory_bandwidth_score": round(mem_bandwidth_score, 2),
                "vram_capacity_score": round(vram_score, 2),
                "cpu_performance_score": round(cpu_score, 2),
                "system_ram_score": round(ram_score, 2),
                "pcie_score": round(pcie_score, 2),
                "weights_inference": cls._WEIGHTS_INFERENCE,
                "weights_finetuning": cls._FINETUNE_WEIGHTS,
                "normalization_inference": cls._NORM_INFERENCE,
                "normalization_finetuning": cls._FINETUNE_NORM
            }
            
            # Build complete evaluation result
            eval_result = {
                # Hardware identification
                "backend_type": "cuda",
                "gpu_name": hw_info["gpu"]["gpu_name"],
                "cpu_model": hw_info["cpu"]["model"],
                
                # Memory metrics
                "total_memory_gb": hw_info["memory"]["total_memory_gb"],
                "available_memory_gb": hw_info["memory"]["available_memory_gb"],
                "memory_bandwidth_gbs": hw_info["gpu"]["memory_bandwidth_gbs"],
                
                # Storage metrics
                "disk_total_gb": hw_info["storage"]["total_gb"],
                "disk_available_gb": hw_info["storage"]["available_gb"],
                
                # Compute metrics
                "estimated_tflops": round(estimated_tflops, 2),
                "tensor_tflops": tensor_tflops,
                "compute_units": hw_info["gpu"]["cuda_cores"],
                "cuda_cores": hw_info["gpu"]["cuda_cores"],  # Entity field name
                "cpu_performance_units": round(cpu_perf_units, 1),
                
                # CUDA specific
                "cuda_version": cuda_version,
                "compute_capability": hw_info["gpu"]["compute_capability"],
                "architecture": architecture,
                "sm_clock_ghz": round(sm_clock_ghz, 3),
                
                # VRAM (CUDA-specific, from hw_info)
                "vram_total_gb": hw_info["gpu"]["vram_total_gb"],
                "vram_available_gb": hw_info["gpu"]["vram_available_gb"],
                
                # Performance scores (0-100)
                "global_inference_score": round(inference_score, 2),
                "global_inference_label": inference_label,
                "global_finetuning_score": round(finetuning_score, 2),
                "global_finetuning_label": finetuning_label,
                "gpu_score": round(gpu_score, 2),
                "cpu_score": round(cpu_score, 2),
                "memory_score": round(vram_score, 2),
                
                # Technical details
                "unified_memory": False,
                "accelerator_available": cuda_available,
                "system_platform": hw_info["system"]["platform"],
                
                # Performance breakdown
                "performance_breakdown": performance_breakdown
            }
            
            logger.info(
                f"Performance evaluation: Inference={inference_score:.1f}/100 ({inference_label}), "
                f"Fine-tuning={finetuning_score:.1f}/100 ({finetuning_label})"
            )
            
            return eval_result
            
        except Exception as e:
            logger.exception(f"Performance evaluation failed: {e}")
            raise HardwareException(
                "Failed to evaluate CUDA performance",
                trace=str(e)
            )

    @classmethod
    def get_flat_hardware_data(cls) -> Dict[str, Any]:
        """Get hardware data in flat format compatible with HardwareProfile entity.
        
        Returns hardware specifications as a flat dictionary ready for database
        insertion. For CUDA backend, get_performance_evaluation() already returns
        data in the correct flat format.
        
        Returns:
            Flat dict with all fields matching HardwareProfile columns.
            
        Raises:
            HardwareException: If hardware data collection fails.
        """
        # get_performance_evaluation() already returns flat structure
        return cls.get_performance_evaluation()
