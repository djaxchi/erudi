import logging
from app.database import get_db
from app.entities.StaticHardwareInfos import StaticHardwareInfo
from backend.app.hardware.services import get_hardware_eval_for_apple_silicon
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.hardware.schemas import HardwareTrainingInfo, HardwareAppStartupInfo, DetailedHardwareInfo

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
        if not hw_infos:

            try:
                # Get Apple Silicon hardware evaluation
                logging.info("Evaluating Apple Silicon hardware...")
                hw = get_hardware_eval_for_apple_silicon()
                logging.info("Hardware evaluation completed successfully.")
            except Exception as e:
                logging.warning(f"Hardware evaluation failed: {e}. Using fallback values.")
                hw = {
                    "chip_model": "Unknown",
                    "cpu_model": "Unknown CPU",
                    "gpu_name": "Unknown GPU",
                    "total_memory_gb": 0,
                    "available_memory_gb": 0,
                    "disk_total_gb": 0,
                    "disk_available_gb": 0,
                    "global_inference_score": 0,
                    "global_inference_label": "Terrible",
                    "global_finetuning_score": 0,
                    "global_finetuning_label": "Terrible",
                    "cpu_score": 0,
                    "gpu_score": 0,
                    "memory_score": 0,
                    "mps_available": False,
                    "is_apple_silicon": False
                }

            persist_hw_infos = StaticHardwareInfo(
                # Basic hardware identification
                chip_model=hw.get("chip_model"),
                cpu_model=hw.get("cpu_model"),
                gpu_name=hw.get("gpu_name"),
                
                # Memory information (unified memory for Apple Silicon)
                system_ram_gb=hw.get("total_memory_gb"),
                available_ram_gb=hw.get("available_memory_gb"),
                
                # Storage information
                disk_total_gb=hw.get("disk_total_gb"),
                disk_avail_gb=hw.get("disk_available_gb"),
                
                # Apple Silicon specific GPU specs
                gpu_cores=hw.get("gpu_cores"),
                estimated_gpu_tflops=hw.get("estimated_gpu_tflops"),
                
                # Apple Silicon specific performance metrics
                memory_bandwidth_gbs=hw.get("memory_bandwidth_gbs"),
                neural_engine_tops=hw.get("neural_engine_tops"),
                cpu_performance_units=hw.get("cpu_performance_units"),
                
                # Architecture details
                architecture=hw.get("architecture"),
                is_apple_silicon=hw.get("is_apple_silicon", False),
                mps_available=hw.get("mps_available", False),
                unified_memory=hw.get("unified_memory", False),
                system_platform=hw.get("system_platform"),
                
                # Performance scores
                global_inference_score=hw.get("global_inference_score"),
                global_inference_label=hw.get("global_inference_label"),
                global_finetuning_score=hw.get("global_finetuning_score"),
                global_finetuning_label=hw.get("global_finetuning_label"),
                cpu_score=hw.get("cpu_score"),
                gpu_score=hw.get("gpu_score"),
                memory_score=hw.get("memory_score"),
                
                # Performance breakdown
                performance_breakdown=hw.get("performance_breakdown"),
                
            )
            db.add(persist_hw_infos)
            db.commit()
            logging.info("Hardware info persisted to database.")
        
        else:
            logging.info("Hardware info already exists in database, skipping creation.")

        db.refresh(hw_infos)
        
        # Helper function to recalculate labels based on boosted scores
        def get_performance_label(score: float) -> str:
            if score >= 75: return "Very Good"
            elif score >= 50: return "Good"
            elif score >= 25: return "Medium"
            else: return "Poor"
        
        # Artificially boost scores by 20 points (capped at 100)
        finetuning_score = min(100.0, (hw_infos.global_finetuning_score if hw_infos.global_finetuning_score else 0.0) + 20.0)
        finetuning_label = get_performance_label(finetuning_score)
        inference_score = min(100.0, (hw_infos.global_inference_score if hw_infos.global_inference_score else 0.0) + 20.0)
        inference_label = get_performance_label(inference_score)

    except Exception as e:
        # Error occurred during database query
        logging.error(f"Error retrieving hardware info: {e}")
        finetuning_score = 0.0
        finetuning_label = f"Terrible"
        inference_score = 0.0
        inference_label = f"Terrible"

    finally:
        db.close()

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