from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Float
from src.database.core import Base
from datetime import datetime


class StaticHardwareInfo(Base):
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