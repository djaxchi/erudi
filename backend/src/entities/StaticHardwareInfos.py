"""SQLAlchemy entity for static hardware specifications and performance scores.

Stores comprehensive hardware profile for Apple Silicon devices, including chip model,
unified memory, GPU specs, performance scores, and detailed breakdown JSON. Persisted
once at app startup and cached for all hardware endpoints.

Example:
    from src.entities.StaticHardwareInfos import StaticHardwareInfo

    hw = StaticHardwareInfo(
        chip_model="M3 Max",
        system_ram_gb=128.0,
        gpu_cores=40,
        global_inference_score=85.0,
        global_inference_label="Very Good"
    )
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Float
from src.database.core import Base
from datetime import datetime


class StaticHardwareInfo(Base):
    """SQLAlchemy model for static hardware specifications and performance scoring.

    Comprehensive hardware profile for Apple Silicon devices, persisted once at startup.
    Includes chip model, unified memory, GPU specs, Neural Engine, performance scores,
    and detailed breakdown JSON.

    Attributes:
        id: Primary key (singleton - only one row).
        chip_model: Apple chip identifier (e.g., "M3 Max", "M2 Pro").
        cpu_model: CPU model string.
        gpu_name: GPU model string.
        system_ram_gb: Total unified memory in GB.
        available_ram_gb: Currently available memory in GB.
        disk_total_gb: Total disk space in GB.
        disk_avail_gb: Available disk space in GB.
        gpu_cores: Number of GPU cores.
        estimated_gpu_tflops: Estimated peak TFLOPS (FP32).
        memory_bandwidth_gbs: Memory bandwidth in GB/s.
        neural_engine_tops: Neural Engine performance in TOPS.
        cpu_performance_units: CPU performance metric.
        architecture: Chip architecture (e.g., "3nm", "5nm").
        is_apple_silicon: True if Apple Silicon (M1/M2/M3/M4).
        mps_available: True if Metal Performance Shaders available.
        unified_memory: True if unified memory architecture.
        system_platform: Platform identifier (e.g., "Darwin").
        global_inference_score: Overall inference score (0-100).
        global_inference_label: Inference performance label.
        global_finetuning_score: Overall fine-tuning score (0-100).
        global_finetuning_label: Fine-tuning performance label.
        cpu_score: CPU-specific score (0-100).
        gpu_score: GPU-specific score (0-100).
        memory_score: Memory-specific score (0-100).
        performance_breakdown: Detailed JSON with per-component metrics.
        created_at: Entity creation timestamp.
        updated_at: Last update timestamp.

    Example:
        >>> hw = StaticHardwareInfo(chip_model="M3 Max", system_ram_gb=128.0, gpu_cores=40)
        >>> hw.global_inference_score = 85.0
    """
    __tablename__ = "static_hardware_infos"

    id = Column(Integer, primary_key=True, index=True)
    
    # Basic hardware identification
    chip_model = Column(String, nullable=True)  # Apple Silicon chip (M1, M2, M3, etc.)
    cpu_model = Column(String, nullable=True)
    gpu_name = Column(String, nullable=True)
    
    # Memory information (unified memory for Apple Silicon)
    system_ram_gb = Column(Float, nullable=True)  # Total unified memory
    available_ram_gb = Column(Float, nullable=True)  # Currently available
    
    # Storage information
    disk_total_gb = Column(Float, nullable=True)
    disk_avail_gb = Column(Float, nullable=True)
    
    # Apple Silicon specific GPU specs
    gpu_cores = Column(Integer, nullable=True)  # Number of GPU cores
    estimated_gpu_tflops = Column(Float, nullable=True)  # Estimated GPU performance
    
    # Apple Silicon specific performance metrics
    memory_bandwidth_gbs = Column(Float, nullable=True)  # Unified memory bandwidth
    neural_engine_tops = Column(Float, nullable=True)  # Neural Engine performance
    cpu_performance_units = Column(Float, nullable=True)  # CPU performance calculation
    
    # Architecture details
    architecture = Column(String, nullable=True)  # 3nm, 5nm, etc.
    is_apple_silicon = Column(Boolean, nullable=True, default=False)
    mps_available = Column(Boolean, nullable=True, default=False)  # Metal Performance Shaders
    unified_memory = Column(Boolean, nullable=True, default=False)  # Unified memory architecture
    system_platform = Column(String, nullable=True)  # Operating system platform
    
    # Performance scores
    global_inference_score = Column(Float, nullable=True)
    global_inference_label = Column(String, nullable=True)
    global_finetuning_score = Column(Float, nullable=True)
    global_finetuning_label = Column(String, nullable=True)
    cpu_score = Column(Float, nullable=True)
    gpu_score = Column(Float, nullable=True)
    memory_score = Column(Float, nullable=True)
    
    # Performance breakdown (stored as JSON for detailed analysis)
    performance_breakdown = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)