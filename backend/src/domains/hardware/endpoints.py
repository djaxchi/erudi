"""REST API endpoints for hardware information and performance scoring.

Provides system hardware detection, scoring, and monitoring endpoints for Apple Silicon
devices. Scores are used to guide UI recommendations for inference and fine-tuning feasibility.

Architecture:
    ┌──────────────┐
    │ Hardware     │
    │ Detection    │ ← get_hardware_eval_for_apple_silicon()
    └───────┬──────┘
            │ (1) Detect chip model (M1/M2/M3/M4 + variant)
            │ (2) Query system RAM, GPU cores, disk space
            │ (3) Compute performance scores (CPU/GPU/Memory)
            ↓
    ┌──────────────┐
    │ StaticHW     │ ← Persisted to database on first startup
    │ InfoEntity   │   (chip, RAM, scores, labels)
    └───────┬──────┘
            │ (3) Endpoints query cached hardware info
            ↓
    ┌──────────────┐
    │ Hardware     │ → /training_info (detailed specs for fine-tuning UI)
    │ Endpoints    │ → /app_startup (boosted scores for dashboard)
    │              │ → /detailed (full debug info)
    └──────────────┘

Scoring System:
    - **CPU Score**: Based on performance cores count and architecture generation.
    - **GPU Score**: Based on GPU cores count and estimated TFLOPS.
    - **Memory Score**: Based on total unified memory (GB).
    - **Inference Score**: Weighted combination (GPU 60%, Memory 30%, CPU 10%).
    - **Fine-tuning Score**: Weighted combination (Memory 50%, GPU 35%, CPU 15%).

Score Labels:
    - 75-100: "Very Good" (recommended for production).
    - 50-74:  "Good" (suitable for most tasks).
    - 25-49:  "Medium" (limited capability).
    - 0-24:   "Poor" (not recommended).

Apple Silicon Specifics:
    - **Unified Memory**: RAM shared between CPU and GPU (no separate VRAM).
    - **MPS (Metal Performance Shaders)**: Apple's GPU acceleration framework.
    - **Neural Engine**: Dedicated AI accelerator (measured in TOPS).
    - **Memory Bandwidth**: Critical for LLM inference speed (GB/s).

Endpoints:
    - GET /hardware/training_info → Detailed specs for fine-tuning UI.
    - GET /hardware/app_startup → Boosted scores for dashboard display (+20 points).
    - GET /hardware/detailed → Full debug info with all specs and breakdown.

Example:
    GET /hardware/app_startup
    Response: {
        "global_inference_score": 85.0,
        "global_inference_label": "Very Good",
        "global_finetuning_score": 75.0,
        "global_finetuning_label": "Very Good"
    }
"""
from src.database.core import get_db
from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session

from src.entities.StaticHardwareInfos import StaticHardwareInfo
from src.utils.hardware_info  import get_hardware_eval_for_apple_silicon
from src.core.logging import logger

from src.domains.hardware.schemas import (
    HardwareTrainingInfo,
    HardwareAppStartupInfo,
    DetailedHardwareInfo
)

router = APIRouter(prefix="/hardware", tags=["hardware"])

@router.get("/training_info", response_model=HardwareTrainingInfo)
def get_hardware_training_info(
    db: Session = Depends(get_db)
):
    """Get detailed hardware specs for fine-tuning UI with Apple Silicon metrics.

    Returns comprehensive hardware information including unified memory, GPU cores,
    TFLOPs estimation, and performance scores. Used by fine-tuning UI to display
    system capabilities and recommend model sizes.

    Args:
        db: Database session injected by FastAPI.

    Returns:
        HardwareTrainingInfo: Full hardware specs with scores and Apple Silicon details.

    Example:
        GET /hardware/training_info
        Response: {
            "chip_model": "M3 Max",
            "total_ram_gb": 128.0,
            "gpu_cores": 40,
            "estimated_gpu_tflops": 14.6,
            "memory_bandwidth_gbs": 400.0,
            "global_finetuning_score": 85.0,
            "global_finetuning_label": "Very Good",
            "unified_memory": true,
            ...
        }
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

@router.get("/app_startup", response_model=HardwareAppStartupInfo)
def get_app_startup_info(
    db: Session = Depends(get_db)
):
    """Get boosted performance scores for application startup dashboard.

    Returns inference and fine-tuning scores with +20 boost (capped at 100) for UI display.
    If hardware info doesn't exist in database, automatically detects and persists it.
    Used by frontend dashboard to show capability badges.

    Args:
        db: Database session injected by FastAPI.

    Returns:
        HardwareAppStartupInfo: Boosted scores with performance labels.

    Note:
        Scores are artificially boosted by 20 points to provide more optimistic UI feedback.
        Real scores are available via /hardware/training_info or /hardware/detailed.

    Example:
        GET /hardware/app_startup
        Response: {
            "global_inference_score": 90.0,  # Real score was 70
            "global_inference_label": "Very Good",
            "global_finetuning_score": 80.0,  # Real score was 60
            "global_finetuning_label": "Very Good"
        }
    """
    try:
        hw_infos = db.query(StaticHardwareInfo).first()
        if not hw_infos:

            try:
                # Get Apple Silicon hardware evaluation
                logger.info("Evaluating Apple Silicon hardware...")
                hw = get_hardware_eval_for_apple_silicon()
                logger.info("Hardware evaluation completed successfully.")
            except Exception as e:
                logger.warning(f"Hardware evaluation failed: {e}. Using fallback values.")
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
            logger.info("Hardware info persisted to database.")
        
        else:
            logger.info("Hardware info already exists in database, skipping creation.")

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
        logger.error(f"Error retrieving hardware info: {e}")
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


@router.get("/detailed", response_model=DetailedHardwareInfo)
def get_detailed_hardware_info(
    db: Session = Depends(get_db)
):
    """Get comprehensive hardware info with all Apple Silicon specs for debugging.

    Returns full hardware profile including raw scores (not boosted), performance breakdown
    JSON, and all Apple Silicon-specific metrics. Used for system diagnostics and debugging.

    Args:
        db: Database session injected by FastAPI.

    Returns:
        DetailedHardwareInfo: Complete hardware profile with all fields populated.

    Example:
        GET /hardware/detailed
        Response: {
            "chip_model": "M3 Max",
            "cpu_model": "Apple M3 Max",
            "gpu_name": "Apple M3 Max GPU",
            "system_ram_gb": 128.0,
            "gpu_cores": 40,
            "estimated_gpu_tflops": 14.6,
            "memory_bandwidth_gbs": 400.0,
            "neural_engine_tops": 18.0,
            "global_inference_score": 70.0,  # Raw score (not boosted)
            "global_finetuning_score": 60.0,  # Raw score (not boosted)
            "performance_breakdown": {"cpu": {...}, "gpu": {...}, "memory": {...}},
            ...
        }
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