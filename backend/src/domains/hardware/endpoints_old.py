"""REST API endpoints for backend-agnostic hardware information.

Provides hardware detection, scoring, and monitoring endpoints across all backends
(MLX/Apple Silicon, CUDA/NVIDIA, CPU fallback). Follows clean architecture with
service layer abstraction.
"""
from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy.orm import Session

from src.database.core import get_db
from src.domains.hardware.repository import Hardware_Repository
from src.domains.hardware.services import Hardware_Service
from src.domains.hardware.schemas import (
    HardwareTrainingInfo,
    HardwareAppStartupInfo,
    DetailedHardwareInfo
)
from src.core.logging import logger
from src.core.exceptions import HardwareException, DatabaseException

router = APIRouter(prefix="/hardware", tags=["hardware"])


def _get_service(db: Session) -> Hardware_Service:
    """Initialize service with repository dependency."""
    repository = Hardware_Repository(db)
    return Hardware_Service(repository)


@router.get("/training_info", response_model=HardwareTrainingInfo)
def get_hardware_training_info(db: Session = Depends(get_db)):
    """Get detailed hardware specs for fine-tuning UI (backend-agnostic)."""
    try:
        service = _get_service(db)
        profile = service.get_or_create_profile()
        
        response = HardwareTrainingInfo(
            backend_type=profile.backend_type,
            cpu_model=profile.cpu_model,
            total_memory_gb=profile.total_memory_gb,
            available_memory_gb=profile.available_memory_gb,
            disk_total_gb=profile.disk_total_gb,
            disk_available_gb=profile.disk_available_gb,
            global_finetuning_score=profile.global_finetuning_score,
            global_finetuning_label=profile.global_finetuning_label,
            global_inference_score=profile.global_inference_score,
            global_inference_label=profile.global_inference_label,
            cpu_score=profile.cpu_score,
            memory_score=profile.memory_score,
            gpu_name=profile.gpu_name,
            estimated_tflops=profile.estimated_tflops,
            memory_bandwidth_gbs=profile.memory_bandwidth_gbs,
            architecture=profile.architecture,
            gpu_score=profile.gpu_score,
            mlx_chip_model=profile.mlx_chip_model,
            mlx_gpu_cores=profile.mlx_gpu_cores,
            mps_available=profile.mps_available,
            neural_engine_tops=profile.neural_engine_tops,
            unified_memory=profile.unified_memory,
            cuda_cores=profile.cuda_cores,
            cuda_version=profile.cuda_version,
            compute_capability=profile.compute_capability,
            vram_total_gb=profile.vram_total_gb,
            vram_available_gb=profile.vram_available_gb
        )
        
        db.commit()
        logger.info(f"Hardware training info retrieved: backend={profile.backend_type}")
        return response
        
    except (HardwareException, DatabaseException) as e:
        db.rollback()
        logger.exception(f"Failed to get hardware training info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception(f"Unexpected error in get_hardware_training_info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/app_startup", response_model=HardwareAppStartupInfo)
def get_app_startup_info(db: Session = Depends(get_db)):
    """Get boosted performance scores for application startup dashboard."""
    try:
        service = _get_service(db)
        profile = service.get_or_create_profile()
        boosted = service.calculate_boosted_scores(profile)
        
        response = HardwareAppStartupInfo(
            backend_type=profile.backend_type,
            global_finetuning_score=boosted["global_finetuning_score"],
            global_finetuning_label=boosted["global_finetuning_label"],
            global_inference_score=boosted["global_inference_score"],
            global_inference_label=boosted["global_inference_label"]
        )
        
        db.commit()
        logger.info(f"App startup info retrieved: backend={profile.backend_type}")
        return response
        
    except (HardwareException, DatabaseException) as e:
        db.rollback()
        logger.exception(f"Failed to get app startup info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception(f"Unexpected error in get_app_startup_info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/detailed", response_model=DetailedHardwareInfo)
def get_detailed_hardware_info(db: Session = Depends(get_db)):
    """Get comprehensive hardware info with all specs for debugging."""
    try:
        service = _get_service(db)
        profile = service.get_or_create_profile()
        
        response = DetailedHardwareInfo(
            backend_type=profile.backend_type,
            cpu_model=profile.cpu_model,
            total_memory_gb=profile.total_memory_gb,
            available_memory_gb=profile.available_memory_gb,
            disk_total_gb=profile.disk_total_gb,
            disk_available_gb=profile.disk_available_gb,
            global_inference_score=profile.global_inference_score,
            global_inference_label=profile.global_inference_label,
            global_finetuning_score=profile.global_finetuning_score,
            global_finetuning_label=profile.global_finetuning_label,
            cpu_score=profile.cpu_score,
            memory_score=profile.memory_score,
            system_platform=profile.system_platform,
            cpu_performance_units=profile.cpu_performance_units,
            performance_breakdown=profile.performance_breakdown,
            gpu_name=profile.gpu_name,
            estimated_tflops=profile.estimated_tflops,
            memory_bandwidth_gbs=profile.memory_bandwidth_gbs,
            architecture=profile.architecture,
            gpu_score=profile.gpu_score,
            mlx_chip_model=profile.mlx_chip_model,
            mlx_gpu_cores=profile.mlx_gpu_cores,
            mps_available=profile.mps_available,
            neural_engine_tops=profile.neural_engine_tops,
            unified_memory=profile.unified_memory,
            cuda_cores=profile.cuda_cores,
            cuda_version=profile.cuda_version,
            compute_capability=profile.compute_capability,
            vram_total_gb=profile.vram_total_gb,
            vram_available_gb=profile.vram_available_gb
        )
        
        db.commit()
        logger.info(f"Detailed hardware info retrieved: backend={profile.backend_type}")
        return response
        
    except (HardwareException, DatabaseException) as e:
        db.rollback()
        logger.exception(f"Failed to get detailed hardware info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception(f"Unexpected error in get_detailed_hardware_info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
