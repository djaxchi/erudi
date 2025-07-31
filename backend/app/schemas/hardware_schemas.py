from pydantic import BaseModel
from typing import Optional


class HardwareTrainingInfo(BaseModel):
    total_ram_gb: float
    available_ram_gb: float
    cpu_model: str
    gpu_model: Optional[str]
    gpu_vram_total_gb: Optional[float]
    gpu_vram_free_gb: Optional[float]
    disk_total_gb: float
    disk_available_gb: float
    cuda_installed: bool
    global_finetuning_score: float
    global_finetuning_label: str
    cpu_eval_score: Optional[float] 
    gpu_eval_score: Optional[float]

class HardwareAppStartupInfo(BaseModel):
    global_finetuning_score: float
    global_finetuning_label: str
    global_inference_score: float
    global_inference_label: str