import logging
from app.database import get_db
from app.models.StaticHardwareInfos import StaticHardwareInfo
from app.utils.hardware_info import get_hardware_eval_for_linux_cpu
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
            disk_total = persist_hw_infos.disk_total_gb
            disk_avail = persist_hw_infos.disk_avail_gb
        else:
            total_ram = avail_ram = disk_total = disk_avail = 0.0
            cpu_model = "Unknown"
    except Exception as e:
        logging.error(f"Error in get_hardware_info: {e}")
        total_ram = avail_ram = disk_total = disk_avail = 0.0
        cpu_model = f"Unknown (error: {e})"

    return HardwareTrainingInfo(
        total_ram_gb=total_ram,
        available_ram_gb=avail_ram,
        cpu_model=cpu_model,
        disk_total_gb=disk_total,
        disk_available_gb=disk_avail,
        global_finetuning_score=persist_hw_infos.global_finetuning_score if persist_hw_infos else 0.0,
        global_finetuning_label=persist_hw_infos.global_finetuning_label if persist_hw_infos else "Terrible",
        cpu_eval_score=persist_hw_infos.cpu_score if persist_hw_infos and persist_hw_infos.cpu_score is not None else None
    )

@router.get("/hardware/app_startup", response_model=HardwareAppStartupInfo)
def get_app_startup_info(
    db: Session = Depends(get_db)
):
    try:
        persist_hw_infos = db.query(StaticHardwareInfo).first()
        if not persist_hw_infos:
            hw = get_hardware_eval_for_linux_cpu()
            persist_hw_infos = StaticHardwareInfo(
                available_ram_gb=hw.get("available_ram_gb", None),
                disk_total_gb=hw.get("disk_total_gb", None),
                disk_avail_gb=hw.get("disk_avail_gb", None),
                cpu_model=hw.get("cpu_model", None),
                system_ram_gb=hw.get("system_ram_gb", None),
                cpu_perf_units=hw.get("cpu_perf_units", None),
                global_inference_score=hw.get("global_inference_score", None),
                global_inference_label=hw.get("global_inference_label", None),
                global_finetuning_score=hw.get("global_finetuning_score", None),
                global_finetuning_label=hw.get("global_finetuning_label", None),
                cpu_score=hw.get("cpu_score", None),
            )
            db.add(persist_hw_infos)
            db.commit()
            db.refresh(persist_hw_infos)
            logging.info("Hardware info persisted to database.")
        else:
            logging.info("Hardware info already exists in database, skipping creation.")
        
        if persist_hw_infos:
            eval_info = {
                "global_finetuning_score": persist_hw_infos.global_finetuning_score,
                "global_finetuning_label": persist_hw_infos.global_finetuning_label,
                "global_inference_score": persist_hw_infos.global_inference_score,
                "global_inference_label": persist_hw_infos.global_inference_label
            }
        else:
            eval_info = None
            failed_label = "No hardware info found in database"
    except Exception as e:
        logging.error(f"Error in get_app_startup_info: {e}")
        eval_info = None
        failed_label = f"Error: {e}"

    return HardwareAppStartupInfo(
        global_finetuning_score = eval_info.get("global_finetuning_score", 0) if eval_info else 0,
        global_finetuning_label = eval_info.get("global_finetuning_label", "Terrible") if eval_info else failed_label or "Terrible",
        global_inference_score = eval_info.get("global_inference_score", 0) if eval_info else 0,
        global_inference_label = eval_info.get("global_inference_label", "Terrible") if eval_info else failed_label or "Terrible",
    )