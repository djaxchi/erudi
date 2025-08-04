from pydantic import BaseModel
from typing import Optional, Dict, Any


class HardwareTrainingInfo(BaseModel):
    """
    Hardware information schema for training/fine-tuning operations.
    Updated for Apple Silicon unified memory architecture.
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
    """
    Hardware information schema for application startup.
    Provides essential performance metrics for UI display.
    """
    global_finetuning_score: float
    global_finetuning_label: str
    global_inference_score: float
    global_inference_label: str


class DetailedHardwareInfo(BaseModel):
    """
    Comprehensive hardware information schema for Apple Silicon systems.
    Includes all available hardware specifications and performance metrics.
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