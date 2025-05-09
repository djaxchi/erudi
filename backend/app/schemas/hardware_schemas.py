from pydantic import BaseModel

class HardwareInfo(BaseModel):
    total_ram_gb: float
    available_ram_gb: float
    cpu_model: str
    gpu_model: str | None
    disk_total_gb: float
    disk_available_gb: float
    cuda_installed: bool
    cuda_path: str | None
