from pydantic import BaseModel
<<<<<<< HEAD
from typing import Optional
=======
from typing import Optional  # Ajout de Optional
>>>>>>> 6851920 (fix - getting and displaying the hardware's components)

class HardwareInfo(BaseModel):
    total_ram_gb: float
    available_ram_gb: float
    cpu_model: str
<<<<<<< HEAD
    gpu_model: Optional[str]
    disk_total_gb: float
    disk_available_gb: float
    cuda_installed: bool
    cuda_path: Optional[str]
=======
    gpu_model: Optional[str]  
    disk_total_gb: float
    disk_available_gb: float
    cuda_installed: bool
    cuda_path: Optional[str]  
>>>>>>> 6851920 (fix - getting and displaying the hardware's components)
