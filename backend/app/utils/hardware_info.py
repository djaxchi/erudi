
"""
Apple Silicon Hardware Detection and Performance Evaluation

DATA ACCURACY DISCLAIMER:
- ✅ OFFICIAL: CPU cores, Neural Engine TOPS, memory bandwidth, max memory, architecture
- ⚠️  ESTIMATED: GPU TFLOPS (Apple doesn't publish these), some performance multipliers
- 📝 VARIABLE: GPU core counts vary by specific model configuration (base vs high-end)

This module provides comprehensive hardware detection for Apple Silicon Macs,
replacing the previous Windows/CUDA-specific code with macOS MPS equivalents.
"""

import logging
import time
import psutil
import cpuinfo
import shutil
import os
import torch
import re
import subprocess
import platform
import json
from pathlib import Path
from typing import Optional, Dict, Any

# --- Apple Silicon GPU Performance Tables ----------------------------
# Apple Silicon chips have unified memory architecture - GPU and CPU share the same memory pool
# NOTE: Some values are official Apple specs, others are estimates based on benchmarks

APPLE_SILICON_SPECS = {
    # M1 Family - Official specs from Apple
    "M1": {
        "gpu_cores": 8,          # 7 or 8-core GPU variants exist (OFFICIAL)
        "memory_bandwidth": 68.25,  # GB/s unified memory bandwidth (OFFICIAL)
        "neural_engine_tops": 11.0,  # Trillion operations per second for ML (OFFICIAL)
        "cpu_cores": {"performance": 4, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 16,        # GB max unified memory (OFFICIAL)
        "architecture": "5nm",   # (OFFICIAL)
        "gpu_cores_note": "Base model has 7 cores, higher-end has 8 cores"
    },
    "M1 Pro": {
        "gpu_cores": 16,         # 14 or 16-core GPU variants (OFFICIAL)
        "memory_bandwidth": 200,  # GB/s (OFFICIAL)
        "neural_engine_tops": 11.0,  # (OFFICIAL)
        "cpu_cores": {"performance": 8, "efficiency": 2},  # (OFFICIAL)
        "max_memory": 32,        # (OFFICIAL)
        "architecture": "5nm",   # (OFFICIAL)
        "gpu_cores_note": "14-core in base, 16-core in higher config"
    },
    "M1 Max": {
        "gpu_cores": 32,         # 24 or 32-core GPU variants (OFFICIAL)
        "memory_bandwidth": 400,  # GB/s (OFFICIAL)
        "neural_engine_tops": 11.0,  # (OFFICIAL)
        "cpu_cores": {"performance": 8, "efficiency": 2},  # (OFFICIAL)
        "max_memory": 64,        # (OFFICIAL)
        "architecture": "5nm",   # (OFFICIAL)
        "gpu_cores_note": "24-core in base, 32-core in higher config"
    },
    "M1 Ultra": {
        "gpu_cores": 64,         # 48 or 64-core GPU (OFFICIAL)
        "memory_bandwidth": 800,  # GB/s (OFFICIAL - 2x M1 Max)
        "neural_engine_tops": 22.0,  # 2x M1 Max (OFFICIAL)
        "cpu_cores": {"performance": 16, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 128,       # (OFFICIAL)
        "architecture": "5nm",   # (OFFICIAL)
        "gpu_cores_note": "48-core in base, 64-core in higher config"
    },
    
    # M2 Family - Official specs from Apple
    "M2": {
        "gpu_cores": 10,         # 8 or 10-core GPU (OFFICIAL)
        "memory_bandwidth": 100,  # GB/s (OFFICIAL)
        "neural_engine_tops": 15.8,  # (OFFICIAL)
        "cpu_cores": {"performance": 4, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 24,        # (OFFICIAL)
        "architecture": "5nm",   # Enhanced 5nm (OFFICIAL)
        "gpu_cores_note": "Base model has 8 cores, higher-end has 10 cores"
    },
    "M2 Pro": {
        "gpu_cores": 19,         # 16 or 19-core GPU (OFFICIAL)
        "memory_bandwidth": 200,  # GB/s (OFFICIAL)
        "neural_engine_tops": 15.8,  # (OFFICIAL)
        "cpu_cores": {"performance": 8, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 32,        # (OFFICIAL)
        "architecture": "5nm",   # Enhanced 5nm (OFFICIAL)
        "gpu_cores_note": "16-core in base, 19-core in higher config"
    },
    "M2 Max": {
        "gpu_cores": 38,         # 30 or 38-core GPU (OFFICIAL)
        "memory_bandwidth": 400,  # GB/s (OFFICIAL)
        "neural_engine_tops": 15.8,  # (OFFICIAL)
        "cpu_cores": {"performance": 8, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 96,        # (OFFICIAL)
        "architecture": "5nm",   # Enhanced 5nm (OFFICIAL)
        "gpu_cores_note": "30-core in base, 38-core in higher config"
    },
    "M2 Ultra": {
        "gpu_cores": 76,         # 60 or 76-core GPU (OFFICIAL)
        "memory_bandwidth": 800,  # GB/s (OFFICIAL - 2x M2 Max)
        "neural_engine_tops": 31.6,  # 2x M2 Max (OFFICIAL)
        "cpu_cores": {"performance": 16, "efficiency": 8},  # (OFFICIAL)
        "max_memory": 192,       # (OFFICIAL)
        "architecture": "5nm",   # Enhanced 5nm (OFFICIAL)
        "gpu_cores_note": "60-core in base, 76-core in higher config"
    },
    
    # M3 Family - Official specs from Apple
    "M3": {
        "gpu_cores": 10,         # 8 or 10-core GPU (OFFICIAL)
        "memory_bandwidth": 100,  # GB/s (OFFICIAL)
        "neural_engine_tops": 18.0,  # (OFFICIAL)
        "cpu_cores": {"performance": 4, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 24,        # (OFFICIAL)
        "architecture": "3nm",   # (OFFICIAL)
        "gpu_cores_note": "Base model has 8 cores, higher-end has 10 cores"
    },
    "M3 Pro": {
        "gpu_cores": 18,         # 14 or 18-core GPU (OFFICIAL)
        "memory_bandwidth": 150,  # GB/s (OFFICIAL)
        "neural_engine_tops": 18.0,  # (OFFICIAL)
        "cpu_cores": {"performance": 6, "efficiency": 6},  # (OFFICIAL)
        "max_memory": 36,        # (OFFICIAL)
        "architecture": "3nm",   # (OFFICIAL)
        "gpu_cores_note": "11-core, 14-core, or 18-core variants exist"
    },
    "M3 Max": {
        "gpu_cores": 40,         # 30 or 40-core GPU (OFFICIAL)
        "memory_bandwidth": 400,  # GB/s (OFFICIAL)
        "neural_engine_tops": 18.0,  # (OFFICIAL)
        "cpu_cores": {"performance": 8, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 128,       # (OFFICIAL)
        "architecture": "3nm",   # (OFFICIAL)
        "gpu_cores_note": "30-core in base, 40-core in higher config"
    },
    
    # M4 Family - Official specs from Apple (as of 2024)
    "M4": {
        "gpu_cores": 10,         # 8 or 10-core GPU (OFFICIAL)
        "memory_bandwidth": 120,  # GB/s (OFFICIAL)
        "neural_engine_tops": 38.0,  # Significantly improved Neural Engine (OFFICIAL)
        "cpu_cores": {"performance": 4, "efficiency": 6},  # (OFFICIAL)
        "max_memory": 32,        # (OFFICIAL)
        "architecture": "3nm",   # Second-gen 3nm (OFFICIAL)
        "gpu_cores_note": "Base model has 8 cores, higher-end has 10 cores"
    },
    "M4 Pro": {
        "gpu_cores": 20,         # Estimated based on M4 pattern (ESTIMATED)
        "memory_bandwidth": 273,  # GB/s (OFFICIAL for M4 Pro)
        "neural_engine_tops": 38.0,  # (OFFICIAL)
        "cpu_cores": {"performance": 10, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 64,        # (OFFICIAL)
        "architecture": "3nm",   # Second-gen 3nm (OFFICIAL)
        "gpu_cores_note": "Actual core count may vary by configuration"
    },
    "M4 Max": {
        "gpu_cores": 40,         # Estimated based on pattern (ESTIMATED)
        "memory_bandwidth": 546,  # GB/s (OFFICIAL for M4 Max)
        "neural_engine_tops": 38.0,  # (OFFICIAL)
        "cpu_cores": {"performance": 12, "efficiency": 4},  # (OFFICIAL)
        "max_memory": 128,       # (OFFICIAL)
        "architecture": "3nm",   # Second-gen 3nm (OFFICIAL)
        "gpu_cores_note": "Actual core count may vary by configuration"
    }
}

# Metal Performance Shaders precision support
# MPS supports various precision formats for ML workloads
# Performance multipliers are ESTIMATES based on typical GPU behavior
MPS_PRECISION_SUPPORT = {
    "fp32": {"supported": True, "performance_multiplier": 1.0},  # Baseline (OFFICIAL)
    "fp16": {"supported": True, "performance_multiplier": 2.0},  # ~2x faster (ESTIMATED)
    "bf16": {"supported": True, "performance_multiplier": 1.8},  # Available on M2+ (ESTIMATED)
    "int8": {"supported": True, "performance_multiplier": 4.0},  # ~4x faster for quantized (ESTIMATED)
}


def mps_runtime_available() -> bool:
    """
    Check if Metal Performance Shaders (MPS) is available on this macOS system.
    MPS is Apple's framework for GPU-accelerated machine learning on Apple Silicon.
    
    Returns:
        bool: True if MPS is available and can be used for PyTorch operations
    """
    return torch.backends.mps.is_available()


def get_mps_memory():
    if torch.backends.mps.is_available():
        try:
            return torch.mps.recommended_max_memory() # en bytes
        except Exception:
            # fallback : prenons 4 GB par défaut
            return 4 * 1024**3
    return None

def get_cpu_memory():
    vm = psutil.virtual_memory()
    return vm.available # en bytes

def build_max_memory(cpu_frac=0.9, mps_frac=0.6):
    max_memory = {}
    
    # CPU
    cpu_mem = get_cpu_memory()
    max_memory["cpu"] = f"{int(cpu_mem * cpu_frac / (1024**3))}GB"
    
    # MPS
    mps_mem = get_mps_memory()
    if mps_mem:
        max_memory["mps"] = f"{int(mps_mem * mps_frac / (1024**3))}GB"

    logging.info(f"Max memory: {max_memory}")
    return max_memory

def get_macos_system_info() -> Dict[str, Any]:
    """
    Get detailed macOS system information using system_profiler command.
    This provides comprehensive hardware details specific to macOS.
    
    Returns:
        Dict containing parsed system information
    """
    try:
        # Run system_profiler to get hardware overview
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("SPHardwareDataType", [{}])[0]
        else:
            return {}
    except Exception as e:
        print(f"Failed to get macOS system info: {e}")
        return {}


def detect_apple_silicon_chip() -> Optional[str]:
    """
    Detect the specific Apple Silicon chip model (M1, M2, M3, M4, etc.).
    This is crucial for determining GPU capabilities and performance characteristics.
    
    Returns:
        Optional[str]: The detected chip model (e.g., "M2 Pro") or None if not detected
    """
    try:
        # Method 1: Use system_profiler to get chip information
        system_info = get_macos_system_info()
        chip_name = system_info.get("chip_type", "")
        
        if chip_name:
            # Clean up the chip name (remove "Apple" prefix if present)
            chip_name = chip_name.replace("Apple ", "")
            
            # Check if it matches our known Apple Silicon specs
            for known_chip in APPLE_SILICON_SPECS.keys():
                if known_chip.lower() in chip_name.lower():
                    return known_chip
        
        # Method 2: Fallback to platform.processor() and parse CPU info
        processor_info = platform.processor()
        if "arm" in processor_info.lower():
            # Try to get more specific info from CPU brand
            try:
                cpu_info = cpuinfo.get_cpu_info()
                brand = cpu_info.get("brand_raw", "").upper()
                
                # Parse M-series chip from brand string
                for chip in APPLE_SILICON_SPECS.keys():
                    if chip.upper() in brand:
                        return chip
            except:
                pass
            
            # Default to M1 if we detect ARM but can't identify specific chip
            return "M1"
        
        return None
        
    except Exception as e:
        print(f"Failed to detect Apple Silicon chip: {e}")
        return None


def get_unified_memory_info() -> Dict[str, float]:
    """
    Get unified memory information for Apple Silicon Macs.
    Unlike traditional systems, Apple Silicon uses unified memory shared between CPU and GPU.
    
    Returns:
        Dict with memory information in GB:
        - total_memory_gb: Total unified memory available
        - available_memory_gb: Currently available memory
        - memory_pressure: Memory pressure level (0.0 to 1.0)
    """
    try:
        # Get virtual memory information using psutil
        vm = psutil.virtual_memory()
        
        total_memory_gb = vm.total / (1024**3)  # Convert bytes to GB
        available_memory_gb = vm.available / (1024**3)
        
        # Calculate memory pressure (higher = more pressure)
        memory_pressure = 1.0 - (vm.available / vm.total)
        
        return {
            "total_memory_gb": round(total_memory_gb, 2),
            "available_memory_gb": round(available_memory_gb, 2),
            "memory_pressure": round(memory_pressure, 3),
            "used_memory_gb": round((vm.total - vm.available) / (1024**3), 2)
        }
        
    except Exception as e:
        print(f"Failed to get unified memory info: {e}")
        return {
            "total_memory_gb": 0.0,
            "available_memory_gb": 0.0,
            "memory_pressure": 0.0,
            "used_memory_gb": 0.0
        }


def get_apple_gpu_info(chip_model: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Apple GPU information based on the detected chip model.
    Apple Silicon integrates GPU cores on the same chip with shared unified memory.
    
    Args:
        chip_model: The detected Apple Silicon chip model
        
    Returns:
        Dict containing GPU specifications and capabilities
    """
    if not chip_model:
        chip_model = detect_apple_silicon_chip()
    
    if not chip_model or chip_model not in APPLE_SILICON_SPECS:
        return {
            "gpu_name": "Unknown Apple GPU",
            "gpu_cores": 0,
            "memory_bandwidth_gbs": 0.0,
            "neural_engine_tops": 0.0,
            "estimated_tflops": 0.0,
            "unified_memory": True,
            "mps_supported": mps_runtime_available()
        }
    
    specs = APPLE_SILICON_SPECS[chip_model]
    
    # ESTIMATE TFLOPS - Apple doesn't publish official GPU TFLOPS
    # This is a rough approximation based on:
    # - Benchmark comparisons with known GPUs
    # - Theoretical compute based on core count and estimated clocks
    # - Real-world performance observations
    # These values should be considered ESTIMATES, not official specs
    estimated_tflops = specs["gpu_cores"] * 0.35  # Conservative estimate: ~0.35 TFLOPS per core
    
    # Add a note about estimation accuracy
    estimation_note = "TFLOPS estimated from benchmarks - Apple doesn't publish official values"
    
    return {
        "gpu_name": f"Apple {chip_model} GPU",
        "gpu_cores": specs["gpu_cores"],
        "memory_bandwidth_gbs": specs["memory_bandwidth"],
        "neural_engine_tops": specs["neural_engine_tops"],
        "estimated_tflops": round(estimated_tflops, 2),
        "tflops_note": estimation_note,
        "unified_memory": True,  # All Apple Silicon uses unified memory
        "mps_supported": mps_runtime_available(),
        "architecture": specs["architecture"],
        "max_memory_gb": specs["max_memory"],
        "gpu_cores_note": specs.get("gpu_cores_note", "Core count may vary by configuration")
    }



def get_macos_cpu_info() -> Dict[str, Any]:
    """
    Get detailed CPU information for macOS systems.
    Focuses on Apple Silicon CPU characteristics.
    
    Returns:
        Dict containing CPU specifications
    """
    try:
        # Get basic CPU info using py-cpuinfo
        cpu_info = cpuinfo.get_cpu_info()
        
        # Get system info for Apple Silicon details
        system_info = get_macos_system_info()
        
        # Detect chip model for detailed specs
        chip_model = detect_apple_silicon_chip()
        
        cpu_specs = {
            "model": cpu_info.get("brand_raw", "Unknown CPU"),
            "architecture": cpu_info.get("arch", "Unknown"),
            "total_cores": psutil.cpu_count(logical=False),  # Physical cores
            "logical_cores": psutil.cpu_count(logical=True),  # Including hyperthreading
            "max_frequency_mhz": None,
            "current_frequency_mhz": None,
        }
        
        # Add Apple Silicon specific details
        if chip_model and chip_model in APPLE_SILICON_SPECS:
            specs = APPLE_SILICON_SPECS[chip_model]
            cpu_specs.update({
                "chip_model": chip_model,
                "performance_cores": specs["cpu_cores"]["performance"],
                "efficiency_cores": specs["cpu_cores"]["efficiency"],
                "architecture_nm": specs["architecture"],
                "is_apple_silicon": True
            })
        else:
            cpu_specs["is_apple_silicon"] = False
        
        # Try to get frequency information (may not be available on Apple Silicon)
        try:
            freq_info = psutil.cpu_freq()
            if freq_info:
                cpu_specs["max_frequency_mhz"] = freq_info.max
                cpu_specs["current_frequency_mhz"] = freq_info.current
        except:
            pass
        
        return cpu_specs
        
    except Exception as e:
        print(f"Failed to get CPU info: {e}")
        return {
            "model": "Unknown CPU",
            "architecture": "Unknown",
            "total_cores": psutil.cpu_count(logical=False) or 4,
            "logical_cores": psutil.cpu_count(logical=True) or 8,
            "is_apple_silicon": False
        }


def get_whole_hardware_info() -> Dict[str, Any]:
    """
    Get comprehensive hardware information for macOS systems.
    Returns complete system snapshot including CPU, GPU, memory, and storage.
    
    Returns:
        Dict containing all hardware information
    """
    try:
        # Get unified memory info (shared between CPU and GPU on Apple Silicon)
        memory_info = get_unified_memory_info()
        
        # Get CPU information
        cpu_info = get_macos_cpu_info()
        
        # Detect Apple Silicon chip and get GPU info
        chip_model = detect_apple_silicon_chip()
        gpu_info = get_apple_gpu_info(chip_model)
        
        # Get storage information for current directory
        disk_usage = psutil.disk_usage(os.getcwd())
        storage_info = {
            "total_gb": round(disk_usage.total / (1024**3), 2),
            "available_gb": round(disk_usage.free / (1024**3), 2),
            "used_gb": round((disk_usage.total - disk_usage.free) / (1024**3), 2),
            "usage_percentage": round(((disk_usage.total - disk_usage.free) / disk_usage.total) * 100, 1)
        }
        
        # Get Metal/MPS framework information
        metal_info = {
            "mps_available": mps_runtime_available(),
            "metal_supported": platform.system() == "Darwin",  # macOS
            "pytorch_mps_support": hasattr(torch.backends, 'mps') and torch.backends.mps.is_built()
        }
        
        return {
            "system": {
                "platform": platform.system(),
                "platform_version": platform.mac_ver()[0] if platform.system() == "Darwin" else None,
                "machine": platform.machine(),
                "processor": platform.processor()
            },
            "cpu": cpu_info,
            "memory": memory_info,
            "gpu": gpu_info,
            "storage": storage_info,
            "metal": metal_info,
            "chip_model": chip_model,
            "timestamp": time.time()
        }
        
    except Exception as e:
        print(f"Failed to get complete hardware info: {e}")
        # Return minimal fallback info
        return {
            "system": {"platform": platform.system()},
            "cpu": {"model": "Unknown", "total_cores": 4},
            "memory": {"total_memory_gb": 8.0, "available_memory_gb": 4.0},
            "gpu": {"gpu_name": "Unknown", "mps_supported": False},
            "storage": {"total_gb": 100.0, "available_gb": 50.0},
            "metal": {"mps_available": False},
            "chip_model": None,
            "timestamp": time.time()
        }


def get_current_available_hardware_info() -> Dict[str, float]:
    """
    Get current available resources (memory, storage) at this moment.
    Useful for monitoring real-time resource availability.
    
    Returns:
        Dict with current available resources in GB
    """
    try:
        # Get current memory status
        memory_info = get_unified_memory_info()
        
        # Get current storage availability
        disk_usage = psutil.disk_usage(os.getcwd())
        available_storage_gb = disk_usage.free / (1024**3)
        
        return {
            "available_memory_gb": memory_info["available_memory_gb"],
            "available_storage_gb": round(available_storage_gb, 2),
            "memory_pressure": memory_info["memory_pressure"],
            "timestamp": time.time()
        }
        
    except Exception as e:
        print(f"Failed to get current hardware info: {e}")
        return {
            "available_memory_gb": 4.0,
            "available_storage_gb": 10.0,
            "memory_pressure": 0.5,
            "timestamp": time.time()
        }


def get_static_hardware_info() -> Dict[str, Any]:
    """
    Get static hardware information that doesn't change during runtime.
    This includes total memory, CPU model, GPU specs, total storage, etc.
    
    Returns:
        Dict containing static hardware specifications
    """
    try:
        hardware_info = get_whole_hardware_info()
        
        # Extract static information that doesn't change
        static_info = {
            "total_memory_gb": hardware_info["memory"]["total_memory_gb"],
            "cpu_model": hardware_info["cpu"]["model"],
            "gpu_name": hardware_info["gpu"]["gpu_name"],
            "gpu_cores": hardware_info["gpu"].get("gpu_cores", 0),
            "total_storage_gb": hardware_info["storage"]["total_gb"],
            "chip_model": hardware_info["chip_model"],
            "mps_available": hardware_info["metal"]["mps_available"],
            "is_apple_silicon": hardware_info["cpu"].get("is_apple_silicon", False),
            "architecture": hardware_info["cpu"].get("architecture_nm", "Unknown"),
            "memory_bandwidth_gbs": hardware_info["gpu"].get("memory_bandwidth_gbs", 0),
            "neural_engine_tops": hardware_info["gpu"].get("neural_engine_tops", 0),
            "platform": hardware_info["system"]["platform"]
        }
        
        return static_info
        
    except Exception as e:
        print(f"Failed to get static hardware info: {e}")
        return {
            "total_memory_gb": 8.0,
            "cpu_model": "Unknown CPU",
            "gpu_name": "Unknown GPU",
            "gpu_cores": 0,
            "total_storage_gb": 100.0,
            "chip_model": None,
            "mps_available": False,
            "is_apple_silicon": False,
            "platform": platform.system()
        }



def warm_up_mps_gpu(seconds: float = 1.0) -> bool:
    """
    Warm up the Apple Silicon GPU using Metal Performance Shaders.
    This helps the GPU reach optimal performance clocks before benchmarking.
    
    Args:
        seconds: How long to run the warm-up workload
        
    Returns:
        bool: True if warm-up was successful, False otherwise
    """
    if not mps_runtime_available():
        print("MPS not available for GPU warm-up")
        return False
    
    try:
        # Create tensors on MPS device for warm-up
        device = torch.device("mps")
        
        # Create matrices for matrix multiplication (computationally intensive)
        size = 2048  # Smaller than CUDA example due to unified memory constraints
        a = torch.randn(size, size, device=device, dtype=torch.float16)
        b = torch.randn(size, size, device=device, dtype=torch.float16)
        
        end_time = time.time() + seconds
        
        # Perform intensive compute operations to warm up GPU
        while time.time() < end_time:
            # Matrix multiplication is compute-intensive and will warm up the GPU
            c = torch.matmul(a, b)
            # Add some additional operations
            d = torch.relu(c)
            e = torch.softmax(d, dim=1)
        
        # Ensure all operations complete
        torch.mps.synchronize()
        
        print(f"MPS GPU warmed up for {seconds} seconds")
        return True
        
    except Exception as e:
        print(f"Failed to warm up MPS GPU: {e}")
        return False


def calculate_cpu_performance_units() -> float:
    """
    Calculate CPU performance units for Apple Silicon.
    This considers both performance and efficiency cores.
    
    Returns:
        float: Estimated CPU performance units
    """
    try:
        cpu_info = get_macos_cpu_info()
        chip_model = cpu_info.get("chip_model")
        
        if chip_model and chip_model in APPLE_SILICON_SPECS:
            specs = APPLE_SILICON_SPECS[chip_model]
            
            # Apple Silicon has performance and efficiency cores with different capabilities
            # Performance cores are ~2-3x more powerful than efficiency cores
            perf_cores = specs["cpu_cores"]["performance"]
            eff_cores = specs["cpu_cores"]["efficiency"]
            
            # Estimate performance units (performance cores weighted higher)
            perf_units = (perf_cores * 3.0) + (eff_cores * 1.0)  # Arbitrary weighting
            
            return perf_units
        else:
            # Fallback for non-Apple Silicon or unknown chips
            cores = psutil.cpu_count(logical=False) or 4
            
            # Try to get frequency information
            try:
                freq_info = psutil.cpu_freq()
                if freq_info and freq_info.max:
                    # Use frequency in GHz
                    freq_ghz = freq_info.max / 1000.0
                    return cores * freq_ghz
                else:
                    # Assume 3.0 GHz average for unknown frequency
                    return cores * 3.0
            except:
                return cores * 3.0
                
    except Exception as e:
        print(f"Failed to calculate CPU performance units: {e}")
        return 8.0  # Default fallback


def calculate_memory_bandwidth_score(chip_model: Optional[str] = None) -> float:
    """
    Calculate memory bandwidth performance score for Apple Silicon.
    Apple Silicon has very high memory bandwidth due to unified memory architecture.
    
    Args:
        chip_model: The Apple Silicon chip model
        
    Returns:
        float: Memory bandwidth in GB/s
    """
    if not chip_model:
        chip_model = detect_apple_silicon_chip()
    
    if chip_model and chip_model in APPLE_SILICON_SPECS:
        return APPLE_SILICON_SPECS[chip_model]["memory_bandwidth"]
    else:
        # Conservative fallback for unknown systems
        return 50.0


# --- Performance Scoring for Apple Silicon / macOS Systems ---

# Weights for calculating overall inference performance score (must sum to 1.0)
WEIGHTS_INFERENCE_MACOS = {
    "gpu_compute": 0.35,      # Apple GPU computational power (reduced from CUDA due to different architecture)
    "memory_bandwidth": 0.30,  # Unified memory bandwidth (very important on Apple Silicon)
    "neural_engine": 0.15,     # Apple Neural Engine for ML acceleration
    "unified_memory": 0.10,    # Total unified memory capacity
    "cpu_performance": 0.05,   # CPU contribution (P-cores + E-cores)
    "system_efficiency": 0.05, # Overall system efficiency and thermal management
}

# Normalization factors for macOS/Apple Silicon performance scoring
NORM_INFERENCE_MACOS = {
    "gpu_tflops": 20.0,       # Apple Silicon GPU TFLOPS (rough estimate for high-end)
    "memory_bandwidth": 400,   # GB/s (M1 Max/Ultra level)
    "neural_engine_tops": 20,  # Trillion operations per second
    "unified_memory": 64,      # GB (comfortable for large models)
    "cpu_units": 20.0,         # CPU performance units
    "efficiency_score": 1.0,   # Perfect efficiency score
}

# Weights for fine-tuning performance (training workloads)
WEIGHTS_FINETUNING_MACOS = {
    "unified_memory": 0.40,    # Memory is crucial for training (higher than inference)
    "gpu_compute": 0.25,       # GPU compute power
    "memory_bandwidth": 0.20,  # Memory bandwidth for large batch processing
    "neural_engine": 0.10,     # Neural Engine can help with certain training ops
    "cpu_performance": 0.05,   # CPU contribution to training pipeline
}

# Normalization factors for fine-tuning
NORM_FINETUNING_MACOS = {
    "unified_memory": 128,     # GB (ideal for training larger models)
    "gpu_tflops": 30.0,        # Higher compute requirements for training
    "memory_bandwidth": 800,   # GB/s (M1 Ultra level for training)
    "neural_engine_tops": 40,  # Higher Neural Engine requirements
    "cpu_units": 25.0,         # Higher CPU performance for training pipelines
}


def get_hardware_eval_for_apple_silicon() -> Dict[str, Any]:
    """
    Calculate comprehensive performance metrics for Apple Silicon Macs.
    This replaces the NVIDIA CUDA evaluation with Apple Silicon specific metrics.
    
    Returns:
        Dict containing detailed performance analysis and scores
    """
    try:
        # Check if MPS is available
        if not mps_runtime_available():
            raise RuntimeError(
                "Metal Performance Shaders (MPS) not available. "
                "Ensure you're running on Apple Silicon with macOS 12.3+ and PyTorch with MPS support."
            )
        
        # Get comprehensive hardware information
        hardware_info = get_whole_hardware_info()
        
        # Extract key components
        chip_model = hardware_info["chip_model"]
        memory_info = hardware_info["memory"]
        gpu_info = hardware_info["gpu"]
        cpu_info = hardware_info["cpu"]
        
        if not chip_model:
            raise RuntimeError("Could not detect Apple Silicon chip model")
        
        # Warm up the GPU for accurate performance measurement
        print(f"Warming up {chip_model} GPU...")
        warm_up_success = warm_up_mps_gpu(1.5)
        
        if not warm_up_success:
            print("Warning: GPU warm-up failed, performance scores may be inaccurate")
        
        # Calculate performance metrics
        
        # 1. GPU Compute Performance
        estimated_tflops = gpu_info.get("estimated_tflops", 0)
        gpu_compute_score = estimated_tflops / NORM_INFERENCE_MACOS["gpu_tflops"]
        
        # 2. Memory Bandwidth Performance
        memory_bandwidth = gpu_info.get("memory_bandwidth_gbs", 0)
        bandwidth_score = memory_bandwidth / NORM_INFERENCE_MACOS["memory_bandwidth"]
        
        # 3. Neural Engine Performance
        neural_engine_tops = gpu_info.get("neural_engine_tops", 0)
        neural_score = neural_engine_tops / NORM_INFERENCE_MACOS["neural_engine_tops"]
        
        # 4. Unified Memory Capacity
        total_memory = memory_info["total_memory_gb"]
        memory_score = total_memory / NORM_INFERENCE_MACOS["unified_memory"]
        
        # 5. CPU Performance
        cpu_units = calculate_cpu_performance_units()
        cpu_score = cpu_units / NORM_INFERENCE_MACOS["cpu_units"]
        
        # 6. System Efficiency (Apple Silicon is generally very efficient)
        efficiency_score = 0.9  # High efficiency for Apple Silicon
        
        # Calculate overall inference score
        inference_score = 100 * (
            WEIGHTS_INFERENCE_MACOS["gpu_compute"] * min(gpu_compute_score, 1.0) +
            WEIGHTS_INFERENCE_MACOS["memory_bandwidth"] * min(bandwidth_score, 1.0) +
            WEIGHTS_INFERENCE_MACOS["neural_engine"] * min(neural_score, 1.0) +
            WEIGHTS_INFERENCE_MACOS["unified_memory"] * min(memory_score, 1.0) +
            WEIGHTS_INFERENCE_MACOS["cpu_performance"] * min(cpu_score, 1.0) +
            WEIGHTS_INFERENCE_MACOS["system_efficiency"] * efficiency_score
        )
        
        # Calculate fine-tuning score with different weights
        finetuning_score = 100 * (
            WEIGHTS_FINETUNING_MACOS["unified_memory"] * min(total_memory / NORM_FINETUNING_MACOS["unified_memory"], 1.0) +
            WEIGHTS_FINETUNING_MACOS["gpu_compute"] * min(estimated_tflops / NORM_FINETUNING_MACOS["gpu_tflops"], 1.0) +
            WEIGHTS_FINETUNING_MACOS["memory_bandwidth"] * min(memory_bandwidth / NORM_FINETUNING_MACOS["memory_bandwidth"], 1.0) +
            WEIGHTS_FINETUNING_MACOS["neural_engine"] * min(neural_engine_tops / NORM_FINETUNING_MACOS["neural_engine_tops"], 1.0) +
            WEIGHTS_FINETUNING_MACOS["cpu_performance"] * min(cpu_units / NORM_FINETUNING_MACOS["cpu_units"], 1.0)
        )
        
        # Performance labels
        def get_performance_label(score: float) -> str:
            if score >= 75: return "Very Good"
            elif score >= 50: return "Good"
            elif score >= 25: return "Medium"
            else: return "Poor"
        
        # Individual component scores for detailed analysis
        gpu_only_score = 100 * min(gpu_compute_score, 1.0)
        cpu_only_score = 100 * min(cpu_score, 1.0)
        memory_only_score = 100 * min(memory_score, 1.0)
        
        # Get current availability
        current_info = get_current_available_hardware_info()
        
        # Compile comprehensive results
        results = {
            # Basic hardware info
            "chip_model": chip_model,
            "gpu_name": gpu_info["gpu_name"],
            "gpu_cores": gpu_info.get("gpu_cores", 0),
            "cpu_model": cpu_info["model"],
            
            # Memory information
            "total_memory_gb": round(total_memory, 1),
            "available_memory_gb": round(current_info["available_memory_gb"], 1),
            "memory_bandwidth_gbs": round(memory_bandwidth, 1),
            
            # Storage information
            "disk_total_gb": round(hardware_info["storage"]["total_gb"], 1),
            "disk_available_gb": round(current_info["available_storage_gb"], 1),
            
            # Performance metrics
            "estimated_gpu_tflops": round(estimated_tflops, 2),
            "neural_engine_tops": round(neural_engine_tops, 1),
            "cpu_performance_units": round(cpu_units, 1),
            
            # Scores
            "global_inference_score": round(inference_score, 1),
            "global_inference_label": get_performance_label(inference_score),
            "global_finetuning_score": round(finetuning_score, 1),
            "global_finetuning_label": get_performance_label(finetuning_score),
            "gpu_score": round(gpu_only_score, 1),
            "cpu_score": round(cpu_only_score, 1),
            "memory_score": round(memory_only_score, 1),
            
            # Technical details
            "mps_available": hardware_info["metal"]["mps_available"],
            "is_apple_silicon": cpu_info.get("is_apple_silicon", False),
            "architecture": gpu_info.get("architecture", "Unknown"),
            "unified_memory": gpu_info.get("unified_memory", True),
            "system_platform": hardware_info["system"]["platform"],
            
            # Performance breakdown for debugging
            "performance_breakdown": {
                "gpu_compute_score": round(gpu_compute_score * 100, 1),
                "memory_bandwidth_score": round(bandwidth_score * 100, 1),
                "neural_engine_score": round(neural_score * 100, 1),
                "memory_capacity_score": round(memory_score * 100, 1),
                "cpu_performance_score": round(cpu_score * 100, 1),
                "efficiency_score": round(efficiency_score * 100, 1)
            }
        }
        
        # Print summary for debugging
        print(f"\n=== Apple Silicon Performance Evaluation ===")
        print(f"Chip: {chip_model}")
        print(f"GPU: {gpu_info['gpu_name']} ({gpu_info.get('gpu_cores', 0)} cores)")
        print(f"Memory: {total_memory:.1f} GB unified @ {memory_bandwidth:.1f} GB/s")
        print(f"Inference Score: {inference_score:.1f} ({get_performance_label(inference_score)})")
        print(f"Fine-tuning Score: {finetuning_score:.1f} ({get_performance_label(finetuning_score)})")
        print(f"==============================================\n")
        
        return results
        
    except Exception as e:
        print(f"Hardware evaluation failed: {e}")
        
        # Return fallback results
        return {
            "chip_model": "Unknown",
            "gpu_name": "Unknown Apple GPU",
            "gpu_cores": 0,
            "cpu_model": "Unknown CPU",
            "total_memory_gb": 8.0,
            "available_memory_gb": 4.0,
            "memory_bandwidth_gbs": 50.0,
            "disk_total_gb": 100.0,
            "disk_available_gb": 50.0,
            "estimated_gpu_tflops": 0.0,
            "neural_engine_tops": 0.0,
            "cpu_performance_units": 8.0,
            "global_inference_score": 20.0,
            "global_inference_label": "Poor",
            "global_finetuning_score": 15.0,
            "global_finetuning_label": "Very Poor",
            "gpu_score": 20.0,
            "cpu_score": 30.0,
            "memory_score": 25.0,
            "mps_available": False,
            "is_apple_silicon": False,
            "architecture": "Unknown",
            "unified_memory": False,
            "system_platform": platform.system(),
            "error": str(e)
        }