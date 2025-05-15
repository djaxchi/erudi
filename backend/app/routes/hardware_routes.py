from fastapi import APIRouter
import psutil, cpuinfo, GPUtil, shutil, os
from app.schemas.hardware_schemas import HardwareInfo

router = APIRouter(tags=["hardware"])

@router.get("/hardware", response_model=HardwareInfo)
def get_hardware_info():
    # Mémoire vive
    vm = psutil.virtual_memory()
    total_ram = vm.total  / (1024**3)
    avail_ram = vm.available / (1024**3)

    # Disque courant
    du = psutil.disk_usage(os.getcwd())
    disk_total = du.total  / (1024**3)
    disk_avail = du.free   / (1024**3)

    # CPU
    info = cpuinfo.get_cpu_info()
    cpu_model = info.get("brand_raw", "Unknown")

    # GPU
    gpus = GPUtil.getGPUs()
    gpu_model = gpus[0].name if gpus else None
    gpu_vram_total = gpus[0].memoryTotal if gpus else None
    gpu_vram_free = gpus[0].memoryFree if gpus else None

    # CUDA
    nvcc_path = shutil.which("nvcc")
    cuda_inst = nvcc_path is not None

    return HardwareInfo(
        total_ram_gb       = round(total_ram, 2),
        available_ram_gb   = round(avail_ram, 2),
        cpu_model          = cpu_model,
        gpu_model          = gpu_model,
        gpu_vram_total_gb  = round(gpu_vram_total, 2) if gpu_vram_total else None,
        gpu_vram_free_gb   = round(gpu_vram_free, 2) if gpu_vram_free else None,
        disk_total_gb      = round(disk_total, 2),
        disk_available_gb  = round(disk_avail, 2),
        cuda_installed     = cuda_inst,
        cuda_path          = nvcc_path,
    )
