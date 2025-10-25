"""Pydantic validation schemas for backend-agnostic hardware information.

Defines response schemas for hardware detection endpoints across all backends
(MLX/CUDA/CPU). Uses discriminated design with backend_type field.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class HardwareProfileBase(BaseModel):
    """Base schema with common fields for all backends."""
    backend_type: str = Field(..., description="Backend type: mlx, cuda, or cpu")
    cpu_model: str
    total_memory_gb: float
    available_memory_gb: float
    disk_total_gb: float
    disk_available_gb: float


class HardwareTrainingInfo(HardwareProfileBase):
    """Hardware profile for training UI with backend-specific fields."""
    global_finetuning_score: float
    global_finetuning_label: str
    global_inference_score: float
    global_inference_label: str
    cpu_score: float
    memory_score: float
    gpu_name: Optional[str] = None
    estimated_tflops: Optional[float] = None
    memory_bandwidth_gbs: Optional[float] = None
    architecture: Optional[str] = None
    gpu_score: Optional[float] = None
    mlx_chip_model: Optional[str] = None
    mlx_gpu_cores: Optional[int] = None
    mps_available: Optional[bool] = None
    neural_engine_tops: Optional[float] = None
    unified_memory: Optional[bool] = None
    cuda_cores: Optional[int] = None
    cuda_version: Optional[str] = None
    compute_capability: Optional[str] = None
    vram_total_gb: Optional[float] = None
    vram_available_gb: Optional[float] = None


class HardwareAppStartupInfo(BaseModel):
    """Essential performance metrics for application startup dashboard."""
    backend_type: str
    global_finetuning_score: float
    global_finetuning_label: str
    global_inference_score: float
    global_inference_label: str


class DetailedHardwareInfo(BaseModel):
    """Comprehensive hardware profile for debugging and diagnostics."""
    backend_type: str
    cpu_model: str
    total_memory_gb: float
    available_memory_gb: float
    disk_total_gb: float
    disk_available_gb: float
    global_inference_score: float
    global_inference_label: str
    global_finetuning_score: float
    global_finetuning_label: str
    cpu_score: float
    memory_score: float
    system_platform: Optional[str] = None
    cpu_performance_units: Optional[float] = None
    performance_breakdown: Optional[Dict[str, Any]] = None
    gpu_name: Optional[str] = None
    estimated_tflops: Optional[float] = None
    memory_bandwidth_gbs: Optional[float] = None
    architecture: Optional[str] = None
    gpu_score: Optional[float] = None
    mlx_chip_model: Optional[str] = None
    mlx_gpu_cores: Optional[int] = None
    mps_available: Optional[bool] = None
    neural_engine_tops: Optional[float] = None
    unified_memory: Optional[bool] = None
    cuda_cores: Optional[int] = None
    cuda_version: Optional[str] = None
    compute_capability: Optional[str] = None
    vram_total_gb: Optional[float] = None
    vram_available_gb: Optional[float] = None
