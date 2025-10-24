"""Pydantic validation schemas for hardware information and performance metrics.

Defines response schemas for hardware detection endpoints, tailored for Apple Silicon
unified memory architecture. Includes performance scores, labels, and detailed specs.

Example:
    from src.domains.hardware.schemas import HardwareAppStartupInfo

    info = HardwareAppStartupInfo(
        global_inference_score=85.0,
        global_inference_label="Very Good",
        global_finetuning_score=75.0,
        global_finetuning_label="Very Good"
    )
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any


class HardwareTrainingInfo(BaseModel):
    """Hardware specs for fine-tuning UI with Apple Silicon unified memory metrics.

    Comprehensive hardware profile including chip model, unified memory, GPU specs,
    and performance scores. Used by fine-tuning UI to recommend model sizes and
    display system capabilities.

    Attributes:
        chip_model: Apple chip identifier (e.g., "M3 Max", "M2 Pro").
        cpu_model: CPU model string.
        gpu_model: GPU model string (Apple Silicon integrated GPU).
        total_ram_gb: Total unified memory in GB (shared CPU/GPU).
        available_ram_gb: Currently available memory in GB.
        gpu_vram_total_gb: Not applicable for unified memory (kept for compatibility).
        disk_total_gb: Total disk space in GB.
        disk_available_gb: Available disk space in GB.
        gpu_cores: Number of GPU cores.
        estimated_gpu_tflops: Estimated peak TFLOPS (FP32).
        memory_bandwidth_gbs: Memory bandwidth in GB/s.
        neural_engine_tops: Neural Engine performance in TOPS.
        architecture: Chip architecture (e.g., "3nm", "5nm").
        is_apple_silicon: True if Apple Silicon (M1/M2/M3/M4).
        mps_available: True if Metal Performance Shaders available.
        unified_memory: True if unified memory architecture.
        global_finetuning_score: Overall fine-tuning score (0-100).
        global_finetuning_label: Performance label (Terrible/Poor/Medium/Good/Very Good).
        cpu_eval_score: CPU-specific score (0-100).
        gpu_eval_score: GPU-specific score (0-100).
        memory_score: Memory-specific score (0-100).
    """
    # Basic hardware identification
    chip_model: Optional[str] = None
    cpu_model: str
    gpu_model: str  # Apple Silicon GPU name
    
    # Memory information (unified memory for Apple Silicon)
    total_ram_gb: float  # Total unified memory
    available_ram_gb: float  # Currently available memory
    gpu_vram_total_gb: Optional[float] = None  # Not applicable for unified memory, kept for compatibility
    
    # Storage information
    disk_total_gb: float
    disk_available_gb: float
    
    # Apple Silicon specific specs
    gpu_cores: Optional[int] = None
    estimated_gpu_tflops: Optional[float] = None
    memory_bandwidth_gbs: Optional[float] = None
    neural_engine_tops: Optional[float] = None
    
    # Architecture details
    architecture: Optional[str] = None  # 3nm, 5nm, etc.
    is_apple_silicon: Optional[bool] = False
    mps_available: Optional[bool] = False
    unified_memory: Optional[bool] = False
    
    # Performance scores
    global_finetuning_score: float
    global_finetuning_label: str
    cpu_eval_score: Optional[float] = None
    gpu_eval_score: Optional[float] = None
    memory_score: Optional[float] = None


class HardwareAppStartupInfo(BaseModel):
    """Essential performance metrics for application startup dashboard.

    Simplified hardware info with boosted scores for UI display. Used by frontend
    dashboard to show capability badges and recommendations.

    Attributes:
        global_finetuning_score: Fine-tuning score (0-100, boosted +20).
        global_finetuning_label: Fine-tuning performance label.
        global_inference_score: Inference score (0-100, boosted +20).
        global_inference_label: Inference performance label.

    Note:
        Scores are boosted by +20 points compared to raw scores (capped at 100).
    """
    global_finetuning_score: float
    global_finetuning_label: str
    global_inference_score: float
    global_inference_label: str


class DetailedHardwareInfo(BaseModel):
    """Comprehensive Apple Silicon hardware profile for debugging and diagnostics.

    Complete hardware specification including all detected metrics, raw scores (not boosted),
    and performance breakdown JSON. Used for system diagnostics and troubleshooting.

    Attributes:
        chip_model: Apple chip identifier (e.g., "M3 Max").
        cpu_model: CPU model string.
        gpu_name: GPU model string.
        system_ram_gb: Total unified memory in GB.
        available_ram_gb: Currently available memory in GB.
        memory_bandwidth_gbs: Memory bandwidth in GB/s.
        disk_total_gb: Total disk space in GB.
        disk_avail_gb: Available disk space in GB.
        gpu_cores: Number of GPU cores.
        estimated_gpu_tflops: Estimated peak TFLOPS (FP32).
        neural_engine_tops: Neural Engine performance in TOPS.
        cpu_performance_units: CPU performance metric.
        architecture: Chip architecture (e.g., "3nm").
        is_apple_silicon: True if Apple Silicon.
        mps_available: True if MPS available.
        unified_memory: True if unified memory architecture.
        system_platform: Platform identifier (e.g., "Darwin").
        global_inference_score: Raw inference score (0-100, not boosted).
        global_inference_label: Inference performance label.
        global_finetuning_score: Raw fine-tuning score (0-100, not boosted).
        global_finetuning_label: Fine-tuning performance label.
        cpu_score: CPU-specific score (0-100).
        gpu_score: GPU-specific score (0-100).
        memory_score: Memory-specific score (0-100).
        performance_breakdown: Detailed JSON with per-component metrics.
    """
    # Basic hardware identification
    chip_model: Optional[str] = None
    cpu_model: Optional[str] = None
    gpu_name: Optional[str] = None
    
    # Memory information
    system_ram_gb: Optional[float] = None
    available_ram_gb: Optional[float] = None
    memory_bandwidth_gbs: Optional[float] = None
    
    # Storage information
    disk_total_gb: Optional[float] = None
    disk_avail_gb: Optional[float] = None
    
    # Apple Silicon GPU specifications
    gpu_cores: Optional[int] = None
    estimated_gpu_tflops: Optional[float] = None
    
    # Apple Silicon performance metrics
    neural_engine_tops: Optional[float] = None
    cpu_performance_units: Optional[float] = None
    
    # Architecture and platform details
    architecture: Optional[str] = None
    is_apple_silicon: Optional[bool] = False
    mps_available: Optional[bool] = False
    unified_memory: Optional[bool] = False
    system_platform: Optional[str] = None
    
    # Performance scores
    global_inference_score: Optional[float] = None
    global_inference_label: Optional[str] = None
    global_finetuning_score: Optional[float] = None
    global_finetuning_label: Optional[str] = None
    cpu_score: Optional[float] = None
    gpu_score: Optional[float] = None
    memory_score: Optional[float] = None
    
    # Detailed performance breakdown
    performance_breakdown: Optional[Dict[str, Any]] = None