from app.database import get_db
from app.models.StaticHardwareInfos import StaticHardwareInfo
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.hardware_schemas import HardwareTrainingInfo, HardwareAppStartupInfo, DetailedHardwareInfo

router = APIRouter(tags=["hardware"])


@router.get("/hardware/training", response_model=HardwareTrainingInfo)
def get_hardware_training_info(
    db: Session = Depends(get_db)
):
    """
    Get hardware information relevant for training/fine-tuning operations.
    Updated for Apple Silicon unified memory architecture.
    """
    try:
        persist_hw_infos = db.query(StaticHardwareInfo).first()
        if persist_hw_infos:
            # Basic hardware info
            chip_model = persist_hw_infos.chip_model
            total_ram = persist_hw_infos.system_ram_gb
            avail_ram = persist_hw_infos.available_ram_gb
            cpu_model = persist_hw_infos.cpu_model
            gpu_model = persist_hw_infos.gpu_name
            
            # Storage info
            disk_total = persist_hw_infos.disk_total_gb
            disk_avail = persist_hw_infos.disk_avail_gb
            
            # Apple Silicon specific specs
            gpu_cores = persist_hw_infos.gpu_cores
            estimated_tflops = persist_hw_infos.estimated_gpu_tflops
            memory_bandwidth = persist_hw_infos.memory_bandwidth_gbs
            neural_engine_tops = persist_hw_infos.neural_engine_tops
            
            # Architecture details
            architecture = persist_hw_infos.architecture
            is_apple_silicon = persist_hw_infos.is_apple_silicon
            mps_available = persist_hw_infos.mps_available
            unified_memory = persist_hw_infos.unified_memory
            
            # Performance scores
            finetuning_score = persist_hw_infos.global_finetuning_score
            finetuning_label = persist_hw_infos.global_finetuning_label
            cpu_score = persist_hw_infos.cpu_score
            gpu_score = persist_hw_infos.gpu_score
            memory_score = persist_hw_infos.memory_score
        else:
            # Fallback values if no hardware info in database
            chip_model = None
            total_ram = 8.0
            avail_ram = 4.0
            cpu_model = "Unknown"
            gpu_model = "Unknown"
            disk_total = 100.0
            disk_avail = 50.0
            gpu_cores = None
            estimated_tflops = None
            memory_bandwidth = None
            neural_engine_tops = None
            architecture = None
            is_apple_silicon = False
            mps_available = False
            unified_memory = False
            finetuning_score = 0.0
            finetuning_label = "Terrible"
            cpu_score = None
            gpu_score = None
            memory_score = None
            
    except Exception as e:
        # Error fallback
        chip_model = None
        total_ram = 8.0
        avail_ram = 4.0
        cpu_model = "Unknown"
        gpu_model = "Unknown"
        disk_total = 100.0
        disk_avail = 50.0
        gpu_cores = None
        estimated_tflops = None
        memory_bandwidth = None
        neural_engine_tops = None
        architecture = None
        is_apple_silicon = False
        mps_available = False
        unified_memory = False
        finetuning_score = 0.0
        finetuning_label = f"Error: {str(e)}"
        cpu_score = None
        gpu_score = None
        memory_score = None

    return HardwareTrainingInfo(
        chip_model=chip_model,
        total_ram_gb=total_ram if total_ram else 0.0,
        available_ram_gb=avail_ram if avail_ram else 0.0,
        cpu_model=cpu_model if cpu_model else "Unknown",
        gpu_model=gpu_model if gpu_model else "Unknown",
        gpu_vram_total_gb=None,  # Not applicable for Apple Silicon unified memory
        disk_total_gb=disk_total if disk_total else 0.0,
        disk_available_gb=disk_avail if disk_avail else 0.0,
        gpu_cores=gpu_cores,
        estimated_gpu_tflops=estimated_tflops,
        memory_bandwidth_gbs=memory_bandwidth,
        neural_engine_tops=neural_engine_tops,
        architecture=architecture,
        is_apple_silicon=is_apple_silicon if is_apple_silicon else False,
        mps_available=mps_available if mps_available else False,
        unified_memory=unified_memory if unified_memory else False,
        global_finetuning_score=finetuning_score if finetuning_score else 0.0,
        global_finetuning_label=finetuning_label if finetuning_label else "Terrible",
        cpu_eval_score=cpu_score,
        gpu_eval_score=gpu_score,
        memory_score=memory_score
    )

@router.get("/hardware/app_startup", response_model=HardwareAppStartupInfo)
def get_app_startup_info(
    db: Session = Depends(get_db)
):
    """
    Get essential hardware performance information for application startup.
    Returns inference and fine-tuning scores for UI display.
    """
    try:
        hw_infos = db.query(StaticHardwareInfo).first()
        if hw_infos:
            # Extract performance scores from database
            finetuning_score = hw_infos.global_finetuning_score
            finetuning_label = hw_infos.global_finetuning_label
            inference_score = hw_infos.global_inference_score
            inference_label = hw_infos.global_inference_label
            
            # Ensure we have valid values
            if finetuning_score is None:
                finetuning_score = 0.0
            if finetuning_label is None:
                finetuning_label = "Terrible"
            if inference_score is None:
                inference_score = 0.0
            if inference_label is None:
                inference_label = "Terrible"
        else:
            # No hardware info found in database
            finetuning_score = 0.0
            finetuning_label = "No hardware info found in database"
            inference_score = 0.0
            inference_label = "No hardware info found in database"
            
    except Exception as e:
        # Error occurred during database query
        finetuning_score = 0.0
        finetuning_label = f"Database error: {str(e)}"
        inference_score = 0.0
        inference_label = f"Database error: {str(e)}"

    return HardwareAppStartupInfo(
        global_finetuning_score=finetuning_score,
        global_finetuning_label=finetuning_label,
        global_inference_score=inference_score,
        global_inference_label=inference_label,
    )


@router.get("/hardware/detailed", response_model=DetailedHardwareInfo)
def get_detailed_hardware_info(
    db: Session = Depends(get_db)
):
    """
    Get comprehensive hardware information including all Apple Silicon specifications.
    Useful for debugging and detailed system analysis.
    """
    try:
        hw_infos = db.query(StaticHardwareInfo).first()
        if not hw_infos:
            # Return empty detailed info if no hardware data available
            return DetailedHardwareInfo()
        
        return DetailedHardwareInfo(
            # Basic hardware identification
            chip_model=hw_infos.chip_model,
            cpu_model=hw_infos.cpu_model,
            gpu_name=hw_infos.gpu_name,
            
            # Memory information
            system_ram_gb=hw_infos.system_ram_gb,
            available_ram_gb=hw_infos.available_ram_gb,
            memory_bandwidth_gbs=hw_infos.memory_bandwidth_gbs,
            
            # Storage information
            disk_total_gb=hw_infos.disk_total_gb,
            disk_avail_gb=hw_infos.disk_avail_gb,
            
            # Apple Silicon GPU specifications
            gpu_cores=hw_infos.gpu_cores,
            estimated_gpu_tflops=hw_infos.estimated_gpu_tflops,
            
            # Apple Silicon performance metrics
            neural_engine_tops=hw_infos.neural_engine_tops,
            cpu_performance_units=hw_infos.cpu_performance_units,
            
            # Architecture and platform details
            architecture=hw_infos.architecture,
            is_apple_silicon=hw_infos.is_apple_silicon,
            mps_available=hw_infos.mps_available,
            unified_memory=hw_infos.unified_memory,
            system_platform=hw_infos.system_platform,
            
            # Performance scores
            global_inference_score=hw_infos.global_inference_score,
            global_inference_label=hw_infos.global_inference_label,
            global_finetuning_score=hw_infos.global_finetuning_score,
            global_finetuning_label=hw_infos.global_finetuning_label,
            cpu_score=hw_infos.cpu_score,
            gpu_score=hw_infos.gpu_score,
            memory_score=hw_infos.memory_score,
            
            # Detailed performance breakdown
            performance_breakdown=hw_infos.performance_breakdown
        )
        
    except Exception as e:
        # Return empty detailed info on error
        return DetailedHardwareInfo()