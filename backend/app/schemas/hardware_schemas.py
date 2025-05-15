from pydantic import BaseModel
from typing import Optional


class HardwareInfo(BaseModel):
    total_ram_gb: float
    available_ram_gb: float
    cpu_model: str
    gpu_model: Optional[str]
    gpu_vram_total_gb: Optional[float]
    gpu_vram_free_gb: Optional[float]
    disk_total_gb: float
    disk_available_gb: float
    cuda_installed: bool
    cuda_path: Optional[str]