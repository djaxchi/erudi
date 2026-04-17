from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Float
from app.database import Base
from datetime import datetime


class StaticHardwareInfo(Base):
    __tablename__ = "static_hardware_infos"

    id = Column(Integer, primary_key=True, index=True)
    available_ram_gb = Column(Float, nullable=True)
    disk_total_gb = Column(Float, nullable=True)
    disk_avail_gb = Column(Float, nullable=True)
    cpu_model = Column(String, nullable=True)
    gpu_name = Column(String, nullable=True)
    vram_total_gb = Column(Float, nullable=True)
    sm_clock_ghz = Column(Float, nullable=True)
    mem_clock_mhz = Column(Integer, nullable=True)  # NVML returns integer MHz
    bus_width_bits = Column(Integer, nullable=True)  # NVML returns integer bits
    mem_bandwidth_gbs = Column(Float, nullable=True)
    compute_cap = Column(String, nullable=True)
    sm_count = Column(Integer, nullable=True)
    cuda_cores_total = Column(Integer, nullable=True)
    fp32_tflops = Column(Float, nullable=True)  # round(fp32_tflops, 2) returns float
    tensor_tflops = Column(JSON, nullable=True)
    system_ram_gb = Column(Float, nullable=True)  # round(..., 1) returns float
    cpu_perf_units = Column(Float, nullable=True)  # round(cpu_units, 1) returns float
    pcie_perf_units = Column(Float, nullable=True)  # round(pcie_units, 1) returns float
    cuda_runtime_available = Column(Boolean, nullable=True)
    cuda_toolkit_path = Column(String, nullable=True)
    global_inference_score = Column(Float, nullable=True)  # 100 * weighted calculation returns float
    global_inference_label = Column(String, nullable=True)
    global_finetuning_score = Column(Float, nullable=True)  # 100 * weighted calculation returns float
    global_finetuning_label = Column(String, nullable=True)
    cpu_score = Column(Float, nullable=True)  # P * 100 returns float
    gpu_score = Column(Float, nullable=True)  # 100 * weighted calculation returns float
    created_at = Column(DateTime, default=datetime.now(), nullable=True)