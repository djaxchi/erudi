import logging
from app.database import get_db
from app.models.StaticHardwareInfos import StaticHardwareInfo
from app.utils.hardware_info import get_hardware_eval_for_NVIDIA_CUDA
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.hardware_schemas import HardwareTrainingInfo, HardwareAppStartupInfo
import torch

router = APIRouter(tags=["hardware"])


@router.get("/hardware/training", response_model=HardwareTrainingInfo)
def get_hardware_info(
    db: Session = Depends(get_db)
):

    try:
        persist_hw_infos = db.query(StaticHardwareInfo).first()
        if persist_hw_infos:
            total_ram = persist_hw_infos.system_ram_gb
            avail_ram = persist_hw_infos.available_ram_gb
            cpu_model = persist_hw_infos.cpu_model
            gpu_model = persist_hw_infos.gpu_name
            gpu_vram_total = persist_hw_infos.vram_total_gb
            disk_total = persist_hw_infos.disk_total_gb
            disk_avail = persist_hw_infos.disk_avail_gb
            cuda_available = persist_hw_infos.cuda_runtime_available
    except Exception as e:
        gpu_eval = None
        failed_label = str(e)

    return HardwareTrainingInfo(
        total_ram_gb=total_ram if total_ram else 0.0,
        available_ram_gb=avail_ram if avail_ram else 0.0,
        cpu_model=cpu_model if cpu_model else "Unknown",
        gpu_model=gpu_model if gpu_model else "Unknown",
        gpu_vram_total_gb=gpu_vram_total if gpu_vram_total else 0.0,
        disk_total_gb=disk_total if disk_total else 0.0,
        disk_available_gb=disk_avail if disk_avail else 0.0,
        cuda_installed=cuda_available if cuda_available is not None else False,
        global_finetuning_score=persist_hw_infos.global_finetuning_score if persist_hw_infos else 0.0,
        global_finetuning_label=persist_hw_infos.global_finetuning_label if persist_hw_infos else "Terrible",
        cpu_eval_score=persist_hw_infos.cpu_score if persist_hw_infos and persist_hw_infos.cpu_score is not None else None,
        gpu_eval_score=persist_hw_infos.gpu_score if persist_hw_infos and persist_hw_infos.gpu_score is not None else None
    )

@router.get("/hardware/app_startup", response_model=HardwareAppStartupInfo)
def get_app_startup_info(
    db: Session = Depends(get_db)
):
    try:
        persist_hw_infos = db.query(StaticHardwareInfo).first()
        if not persist_hw_infos:
            hw = get_hardware_eval_for_NVIDIA_CUDA()
            persist_hw_infos = StaticHardwareInfo(
                available_ram_gb=hw.get("available_ram_gb", None),
                disk_total_gb=hw.get("disk_total_gb", None),
                disk_avail_gb=hw.get("disk_avail_gb", None),
                gpu_name=hw.get("gpu_name", "Unknown"),
                cpu_model=hw.get("cpu_model", None),
                vram_total_gb=hw.get("vram_total_gb", None),
                sm_clock_ghz=hw.get("sm_clock_ghz", None),
                mem_clock_mhz=hw.get("mem_clock_mhz", None),
                bus_width_bits=hw.get("bus_width_bits", None),
                mem_bandwidth_gbs=hw.get("mem_bandwidth_gbs", None),
                compute_cap=hw.get("compute_cap", None),
                sm_count=hw.get("sm_count", None),
                cuda_cores_total=hw.get("cuda_cores_total", None),
                fp32_tflops=hw.get("fp32_tflops", None),
                tensor_tflops=hw.get("tensor_tflops", None),
                system_ram_gb=hw.get("system_ram_gb", None),
                cpu_perf_units=hw.get("cpu_perf_units", None),
                pcie_perf_units=hw.get("pcie_perf_units", None),
                cuda_runtime_available=hw.get("cuda_runtime_available", None),
                cuda_toolkit_path=hw.get("cuda_toolkit_path", None),
                global_inference_score=hw.get("global_inference_score", None),
                global_inference_label=hw.get("global_inference_label", None),
                global_finetuning_score=hw.get("global_finetuning_score", None),
                global_finetuning_label=hw.get("global_finetuning_label", None),
                cpu_score=hw.get("cpu_score", None),
                gpu_score=hw.get("gpu_score", None),
            )
            db.add(persist_hw_infos)
            db.commit()
            db.refresh(persist_hw_infos)
            logging.info("Hardware info persisted to database.")
        else:
            logging.info("Hardware info already exists in database, skipping creation.")
        
        if persist_hw_infos:
            gpu_eval = {
                "global_finetuning_score": persist_hw_infos.global_finetuning_score,
                "global_finetuning_label": persist_hw_infos.global_finetuning_label,
                "global_inference_score": persist_hw_infos.global_inference_score,
                "global_inference_label": persist_hw_infos.global_inference_label
            }
        else:
            gpu_eval = None
            failed_label = "No hardware info found in database"
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
def has_cuda(
    db: Session = Depends(get_db)
):
    """
    Check if the system has NVIDIA CUDA installed.
    """
    try:
        persist_hw_infos = db.query(StaticHardwareInfo).first()
        cuda_available = persist_hw_infos.cuda_runtime_available if persist_hw_infos else torch.cuda.is_available() 
        return {"has_cuda": cuda_available}
    except Exception as e:
        return {"has_cuda": False, "error": str(e)}