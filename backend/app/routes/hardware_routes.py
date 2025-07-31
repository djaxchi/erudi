from ..utils.hardware_info import get_whole_hardware_info, get_hardware_eval_for_NVIDIA_CUDA
from fastapi import APIRouter
from app.schemas.hardware_schemas import HardwareTrainingInfo, HardwareAppStartupInfo

router = APIRouter(tags=["hardware"])


@router.get("/hardware/training", response_model=HardwareTrainingInfo)
def get_hardware_info():

    total_ram, avail_ram, cpu_model, gpu_model, gpu_vram_total, gpu_vram_free, disk_total, disk_avail, cuda_available, cuda_toolkit_path = get_whole_hardware_info()
    try:
        gpu_eval = get_hardware_eval_for_NVIDIA_CUDA()
    except Exception as e:
        gpu_eval = None
        failed_label = str(e)

    return HardwareTrainingInfo(
        total_ram_gb       = round(total_ram, 2),
        available_ram_gb   = round(avail_ram, 2),
        cpu_model          = cpu_model,
        gpu_model          = gpu_model,
        gpu_vram_total_gb  = round(gpu_vram_total, 2) if gpu_vram_total else None,
        gpu_vram_free_gb   = round(gpu_vram_free, 2) if gpu_vram_free else None,
        disk_total_gb      = round(disk_total, 2),
        disk_available_gb  = round(disk_avail, 2),
        cuda_installed     = cuda_available,
        global_finetuning_score = gpu_eval.get("global_finetuning_score", 0) if gpu_eval else 0,
        global_finetuning_label = gpu_eval.get("global_finetuning_label", "Terrible") if gpu_eval else failed_label or "Terrible",
        cpu_eval_score     = gpu_eval.get("cpu_score", 0) if gpu_eval else None,
        gpu_eval_score     = gpu_eval.get("gpu_score", 0) if gpu_eval else None
    )

@router.get("/hardware/app_startup", response_model=HardwareAppStartupInfo)
def get_app_startup_info():
    try:
        gpu_eval = get_hardware_eval_for_NVIDIA_CUDA()
    except Exception as e:
        gpu_eval = None
        failed_label = str(e)

    return HardwareAppStartupInfo(
        global_finetuning_score = gpu_eval.get("global_finetuning_score", 0) if gpu_eval else 0,
        global_finetuning_label = gpu_eval.get("global_finetuning_label", "Terrible") if gpu_eval else failed_label or "Terrible",
        global_inference_score = gpu_eval.get("global_inference_score", 0) if gpu_eval else 0,
        global_inference_label = gpu_eval.get("global_inference_label", "Terrible") if gpu_eval else failed_label or "Terrible",
    )

@router.get("/hardware/has_cuda")
def has_cuda():
    """
    Check if the system has NVIDIA CUDA installed.
    """
    try:
        cuda_available = get_whole_hardware_info()[8]  # Get CUDA availability
        return {"has_cuda": cuda_available}
    except Exception as e:
        return {"has_cuda": False, "error": str(e)}