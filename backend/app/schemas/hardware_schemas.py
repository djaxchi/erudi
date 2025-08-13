from pydantic import BaseModel
from typing import Optional


class HardwareTrainingInfo(BaseModel):
    total_ram_gb: float
    available_ram_gb: float
    cpu_model: str
    disk_total_gb: float
    disk_available_gb: float
    global_finetuning_score: float
    global_finetuning_label: str
    cpu_eval_score: Optional[float]
class HardwareAppStartupInfo(BaseModel):
    global_finetuning_score: float
    global_finetuning_label: str
    global_inference_score: float
    global_inference_label: str