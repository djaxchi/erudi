"""Database initialization and seeding for application startup.

This module handles:
- Table creation via SQLAlchemy ORM
- Seeding default LLM models from HuggingFace
- Cleaning up interrupted jobs from previous sessions
- Initializing hardware metrics and startup variables

Seeding Strategy:
    1. **Base Models**: Curated list of supported quantized models
       (Gemma 1B/2B/4B/12B, Mistral 7B, Ministral 8B, Mistral-Nemo 12B)
    2. **Derived Models**: Top 30 quality models per base model family,
       filtered by downloads/likes and excluding quantized variants
    3. **Job Recovery**: Mark incomplete download/training/KB jobs as failed
    4. **Hardware Profiling**: Persist static system capabilities

Quality Filters:
    - Minimum 50 downloads and 5 likes
    - Exclude pre-quantized models (GGUF, GPTQ, AWQ, etc.)
    - Prioritize instruction-tuned, chat, and reasoning models
    - Skip test/debug/experimental checkpoints

Architecture:
    Startup Flow:
    ┌────────────────────────────────────────────────────────────┐
    │ createTables()                                             │
    │  └─> Create all SQLAlchemy tables if not exist            │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ startup_populate_database()                                │
    │  1. add_base_models()       → Quantized core models       │
    │  2. add_derived_models()    → Quality derived models      │
    │  3. mark_unfinished_jobs_as_failed() → Cleanup jobs       │
    │  4. initialize_hardware_info() → Persist capabilities     │
    │  5. initialize_startup_variables() → First-run flags      │
    └────────────────────────────────────────────────────────────┘

Example:
    Called automatically during FastAPI lifespan startup::

        from src.database.seed import createTables, startup_populate_database

        async def lifespan(app: FastAPI):
            await createTables()
            await startup_populate_database()
            yield
            # Cleanup...

    Manual database reset (development only)::

        from src.database.seed import delete_all_data

        await delete_all_data()  # Interactive confirmation required

Note:
    - Base models use engine-specific MODEL_MAPPING for quantized links
    - Derived models are fetched from HuggingFace search (200 max checked)
    - Job cleanup prevents zombie processes and disk space leaks
    - Hardware info is evaluated once and cached in database

Warning:
    delete_all_data() is destructive and requires interactive confirmation.
    Never call in production. Use migrations for schema changes.
"""

# TODO CLEANING OF THE WHOLE FILE


import os, shutil
from datetime import datetime

from src.core.logging import logger
from src.core.config import (
    HF_API
)
from src.core import config

from sqlalchemy.orm import Session
from src.database.core import (
    Base,
    db_engine,
    SessionLocal
)

from src.utils.hf_model_metadata import *

from src.entities.Conversation import Conversation
from src.entities.Llm import Llm
from src.entities.Message import Message
from src.entities.TrainingJob import TrainingJob
from src.entities.DownloadJob import DownloadJobModel
from src.entities.StaticHardwareInfos import StaticHardwareInfo
from src.entities.VectorStore import VectorStore
from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.KBJob import KBJobModel
from src.entities.StartupVariables import StartupVariables


async def createTables():
    """Create all database tables from SQLAlchemy models.

    Uses metadata from Base to create tables for:
    - Llm, Conversation, Message
    - TrainingJob, DownloadJobModel, KBJobModel
    - KnowledgeBase, VectorStore
    - StaticHardwareInfo, StartupVariables

    Returns:
        None. Tables are created idempotently (if not exists).

    Example:
        ::

            from src.database.seed import createTables

            await createTables()
            # All tables now exist in SQLite database
    """
    # Create all tables in the database
    Base.metadata.create_all(bind=db_engine)

async def delete_all_data() -> None :
    """Delete all data from the database and file storage (DESTRUCTIVE).

    This function performs a complete wipe of:
    - All database records (models, conversations, jobs, etc.)
    - Downloaded model files (data/models/)
    - FAISS vector indexes (data/indexes/)

    Requires interactive confirmation before proceeding.

    Returns:
        None. Database and directories are purged after confirmation.

    Example:
        ::

            from src.database.seed import delete_all_data

            await delete_all_data()
            # Prompt: "Are you sure you want to do this? (y/n)"
            # If "y": All data deleted
            # If "n": Operation cancelled

    Warning:
        This is a destructive operation with no undo. Use only in development.
        Never expose this function in production endpoints.
    """
    # Delete all data from the database
    logger.debug("Preparing to delete all data from the database.")
    res = input("Are you sure you want to do this ? (y/n)")
    if res != "y" and res != "yes":
        logger.debug("Database deletion cancelled.")
        return
    logger.debug("Deleting...")
    db: Session = SessionLocal()
    try:
        
        if os.path.exists("data/models"):
            shutil.rmtree("data/models")
        os.makedirs("data/models", exist_ok=True)
        if os.path.exists("data/indexes"):
            shutil.rmtree("data/indexes")
        os.makedirs("data/indexes", exist_ok=True)
        db.query(Llm).delete()
        db.query(Conversation).delete()
        db.query(Message).delete()
        db.query(TrainingJob).delete()
        db.query(DownloadJobModel).delete()
        db.query(StaticHardwareInfo).delete()
        db.query(VectorStore).delete()
        db.query(KnowledgeBase).delete()
        db.query(KBJobModel).delete()
        db.query(StartupVariables).delete()

        db.commit()
        logger.debug("All data deleted successfully.")
    except Exception as e:
        logger.error(f"Error deleting data: {e}")
        db.rollback()
    finally:
        db.close()

async def startup_populate_database():
    """Populate database with default models and initialize runtime state.

    Orchestrates the full seeding workflow:
    1. Add base models (quantized core models)
    2. Add derived models (quality HuggingFace models)
    3. Mark unfinished jobs as failed (cleanup from previous crash)
    4. Initialize hardware info (system capabilities)
    5. Initialize startup variables (first-run flags)

    Returns:
        None. Database is populated or exception is raised.

    Raises:
        Exception: If any seeding step fails (HuggingFace API errors,
            database write failures, hardware detection failures).
            Rolls back transaction and re-raises.

    Example:
        ::

            from src.database.seed import startup_populate_database

            await startup_populate_database()
            # Database now contains:
            # - 7 base models (Gemma, Mistral families)
            # - ~210 derived models (30 per base model)
            # - Hardware metrics
            # - Startup flags

    Note:
        This function is idempotent for base models (skips existing).
        Derived models are re-fetched if database was wiped.
    """

    db: Session = SessionLocal()
    try:
        add_base_models(db, HF_API)
        add_derived_models(db, HF_API)
        mark_unfinished_jobs_as_failed(db)
        initialize_hardware_info(db)
        initialize_startup_variables(db)
        logger.info("Startup database population completed successfully.")
    except Exception as e:
        logger.error(f"Error during startup population: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# ----------------------------
# Sub-functions
# ----------------------------

# TODO FIX TO MAKE IT ENGINE-AGNOSTIC AS IT IS NOW IN ENGINE
def add_base_models(db: Session, HF_API):
    """Add curated list of base models with quantized links.

    Seeds the database with 7 core models across Gemma and Mistral families.
    Uses engine-specific MODEL_MAPPING to prefer quantized variants (MLX, GGUF).

    Args:
        db: Active SQLAlchemy session for database operations.
        HF_API: HuggingFace API client for fetching model metadata.

    Returns:
        None. Models are committed to database via session.

    Note:
        Existing models (by name) are skipped to avoid duplicates.
        Falls back to size estimates if HuggingFace API fails.
    """
    base_models = [
        ("Gemma-1B", "google/gemma-3-1b-it", "gemma"),
        ("Gemma-2B", "google/gemma-2-2b-it", "gemma"),
        ("Gemma-4B", "google/gemma-3-4b-it", "gemma"),
        ("Mistral-7B", "mistralai/Mistral-7B-Instruct-v0.3", "mistral"),
        ("Ministral-8B", "mistralai/Ministral-8B-Instruct-2410", "mistral"),
        ("Gemma-12B", "google/gemma-3-12b-it", "gemma"),
        ("Mistral-Nemo-12B", "mistralai/Mistral-Nemo-Instruct-2407", "mistral"),
    ]

    for name, link, model_type in base_models:
        existing_model = db.query(Llm).filter(Llm.name == name).first()
        param_str = get_parameter_count_from_name(name, link)
        if "B" in param_str:
            param_size = float(param_str.replace("B", ""))
        elif "M" in param_str:
            param_size = float(param_str.replace("M", "")) / 1000
        else:
            param_size = -1.0  # Unknown

        if existing_model:
            continue

        try:
            quant_link = config.LLM_Engine.MODEL_MAPPING.get(link)
            is_quantized = quant_link is not None
            model_info = HF_API.model_info(link)
            size_estimate = get_disk_size_after_quant(quant_link) if is_quantized else get_model_size_estimate(name, link)
            actual_link = quant_link if is_quantized else link

            llm = Llm(
                name=name,
                local=0,
                link=actual_link,
                type=model_type,
                quantized=1 if is_quantized else 0,
                model_metadata=format_model_info_metadata(model_info, size_estimate, is_quantized),
                param_size=param_size
            )
            db.add(llm)
            logger.info(f"Added base model {name} (quantized={is_quantized}) with metadata and size: {size_estimate}")
        except Exception as e:
            logger.warning(f"Error fetching metadata for {name}: {e}")
            # fallback
            quant_link = config.LLM_Engine.MODEL_MAPPING.get(link)
            is_quantized = quant_link is not None
            size_estimate = get_disk_size_after_quant(quant_link) if is_quantized else get_model_size_estimate(name, link)
            actual_link = quant_link if is_quantized else link
            fallback_metadata = f"Size: {size_estimate}\nModel ID: {link}\nQuantized: {is_quantized}\nAuthor: Unknown\nLibrary: Unknown"

            llm = Llm(
                name=name,
                local=0,
                link=actual_link,
                type=model_type,
                quantized=1 if is_quantized else 0,
                model_metadata=fallback_metadata,
                param_size=param_size
            )
            db.add(llm)
            logger.info(f"Added base model {name} (quantized={is_quantized}) with size estimate: {size_estimate}")

def is_quality_model_from_hf_search(model_info):
    """Filter HuggingFace models by quality metrics and tags.

    Args:
        model_info: HuggingFace ModelInfo object with downloads, likes, tags.

    Returns:
        bool: True if model meets quality thresholds, False otherwise.

    Quality Criteria:
        - Minimum 50 downloads and 5 likes
        - Contains interesting tags (instruction-tuned, chat, reasoning, etc.)
        - OR contains quality keywords in model ID (instruct, assistant, etc.)

    Note:
        Used by add_derived_models() to filter ~200 candidates to top 30.
    """
    MIN_DOWNLOADS = 50
    MIN_LIKES = 5
    INTERESTING_TAGS = [
        "instruction-tuned", "chat", "conversational", "assistant",
        "code", "math", "reasoning", "multilingual", "translation",
        "summarization", "question-answering", "creative-writing",
        "roleplay", "medical", "legal", "science", "education",
        "storytelling", "dialogue", "text-generation"
    ]

    if model_info.downloads < MIN_DOWNLOADS or model_info.likes < MIN_LIKES:
        return False
    if model_info.tags and any(tag in INTERESTING_TAGS for tag in model_info.tags):
        return True
    quality_keywords = ["instruct", "chat", "assistant", "tuned", "fine-tuned",
                        "trained", "optimized", "enhanced", "improved"]
    if any(keyword in model_info.modelId.lower() for keyword in quality_keywords):
        return True
    return False

def add_derived_models(db: Session, HF_API):
    """Add top quality derived models from HuggingFace per base model family.

    Searches HuggingFace for each base model family (Gemma, Mistral) and adds
    the top 30 quality models sorted by downloads. Excludes pre-quantized
    models and test/debug checkpoints.

    Args:
        db: Active SQLAlchemy session for database operations.
        HF_API: HuggingFace API client for model search.

    Returns:
        None. Models are committed to database after each family.

    Note:
        - Checks up to 200 models per family to find top 30 quality models
        - Skips GGUF, GPTQ, AWQ, 4bit, 8bit, LoRA, and test checkpoints
        - Skips base model IDs to avoid duplicates with add_base_models()
        - Parameter size inferred from name or fallback to family default
    """
    base_model_searches = [
        ("Mistral-7B v0.3", "mistral", 7.0),
        ("Gemma 1B", "gemma", 1.0),
        ("Gemma 2B", "gemma", 2.0),
        ("Gemma 4B", "gemma", 4.0),
        ("Ministral-8B", "mistral", 8.0),
        ("Gemma 12B", "gemma", 12.0),
        ("Mistral-Nemo-12B", "mistral", 12.0)
    ]
    TOP_MODELS_PER_BASE = 30
    SKIP_IDS = [
        "mistral-7b-instruct-v0.3",
        "mistral-7b-v0.3",
        "gemma-3-1b-it",
        "gemma-2-2b-it",
        "gemma-3-4b-it",
        "ministral-8b-instruct-2410",
        "gemma-3-12b-it",
        "mistral-nemo-instruct-2407"
    ]
    SKIP_TERMS = [
        "gguf","gptq","bnb","4bit","8bit","f16","awq",
        "q4","q5","q6", "q8", "fp8","fp16","fp4","sqft", 'quantized',
        "quant", "quantized", "quantization", "lora", "knut",
        "sft", "int4", "int8", "int16", "int32", "int64",
        "peft", "test", "untrained", "checkpoint", "tmp", "temp",
        "debug", "draft", "experiment", "eval", "benchmark", "pt", "onnx","abliterated","E2B"
    ]

    for search_term, model_type, default_param_size in base_model_searches:
        logger.info(f"Fetching top {TOP_MODELS_PER_BASE} quality derived models for {search_term}...")
        added_count = 0
        checked_count = 0
        for m in HF_API.list_models(search=search_term, sort="downloads", direction=-1):
            if added_count >= TOP_MODELS_PER_BASE:
                break
            checked_count += 1
            if checked_count > 200:
                break
            mid = m.modelId.lower()
            mname = mid.split("/")[-1].lower()
            if mname in SKIP_IDS or any(term in mid for term in SKIP_TERMS):
                continue
            exists = db.query(Llm).filter_by(link=m.modelId).first()
            if exists or not is_quality_model_from_hf_search(m):
                continue
            size_estimate = get_model_size_estimate(m.modelId.split("/")[-1], m.modelId)
            param_str = get_parameter_count_from_name(m.modelId.split("/")[-1], m.modelId)
            if "B" in param_str:
                param_size = float(param_str.replace("B", ""))
            elif "M" in param_str:
                param_size = float(param_str.replace("M", "")) / 1000
            else:
                param_size = default_param_size

            llm_entry = Llm(
                name=m.modelId.split("/")[-1],
                local=0,
                link=m.modelId,
                type=model_type,
                quantized=0,
                model_metadata=format_model_info_metadata(m, size_estimate, quantized=False),
                param_size=param_size
            )
            db.add(llm_entry)
            added_count += 1
            logger.info(f"  Added {m.modelId.split('/')[-1]} ({added_count}/{TOP_MODELS_PER_BASE}) - {m.downloads} downloads, {m.likes} likes")
        db.commit()

def mark_unfinished_jobs_as_failed(db: Session):
    """Mark interrupted jobs from previous sessions as failed and cleanup resources.

    Handles three job types:
    - DownloadJobModel: Delete incomplete model files, reset local_model_id
    - TrainingJob: Delete partial training checkpoints, reset llm_id
    - KBJobModel: Delete incomplete FAISS indexes, cleanup knowledge base

    Args:
        db: Active SQLAlchemy session for database operations.

    Returns:
        None. Job statuses updated and orphaned resources deleted.

    Note:
        This prevents zombie processes, disk space leaks, and database
        inconsistencies from application crashes or forced shutdowns.
    """
    # Download jobs
    unfinished_jobs = db.query(DownloadJobModel).filter(
        DownloadJobModel.status.in_(["running", "pending"])
    ).all()
    for job in unfinished_jobs:
        job.status = "failed"
        llm = db.query(Llm).filter(Llm.id == job.local_model_id).first()
        if llm and os.path.exists(llm.link):
            shutil.rmtree(llm.link, ignore_errors=True)
            db.delete(llm)
        if job.temp_local_model_link and os.path.exists(job.temp_local_model_link):
            shutil.rmtree(job.temp_local_model_link, ignore_errors=True)
            job.temp_local_model_link = ""
        job.error_message = "Downloading was not completed due to application shutdown."
        job.local_model_id = -1
        job.updated_at = datetime.now()
        job.local_model_link = ""
        db.commit()
        logger.warning(f"Marked unfinished job {job.id} as failed.")

    # Training jobs
    unfinished_jobs = db.query(TrainingJob).filter(
        TrainingJob.status.in_(["running", "pending"])
    ).all()
    for job in unfinished_jobs:
        job.status = "failed"
        job.error_message = "Training was not completed due to application shutdown."
        llm = db.query(Llm).filter(Llm.id == job.llm_id).first()
        if llm and os.path.exists(llm.link):
            shutil.rmtree(llm.link, ignore_errors=True)
            db.delete(llm)
        job.llm_id = -1
        job.updated_at = datetime.now()
        db.commit()
        logger.warning(f"Marked unfinished TrainingJob {job.id} as failed.")

    # KB jobs
    unfinished_jobs = db.query(KBJobModel).filter(
        KBJobModel.status.in_(["running", "pending"])
    ).all()
    for job in unfinished_jobs:
        job.status = "failed"
        job.error_message = "Knowledge Base creation was not completed due to application shutdown."
        new_llm = db.query(Llm).filter(Llm.id == job.new_model_id).first()
        if new_llm:
            db.delete(new_llm)
        vector_store = db.query(VectorStore).filter(VectorStore.kb_id == job.kb_id).first()
        if vector_store:
            db.delete(vector_store)
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == job.kb_id).first()
        if kb and kb.index_path and os.path.exists(kb.index_path):
            shutil.rmtree(kb.index_path, ignore_errors=True)
            db.delete(kb)
        job.new_model_id = -1
        job.updated_at = datetime.now()
        db.commit()
        logger.warning(f"Marked unfinished KBJob {job.id} as failed.")

def initialize_hardware_info(db: Session):
    """Evaluate and persist system hardware capabilities.

    Runs hardware detection once on first startup and caches results in
    StaticHardwareInfo table. Subsequent startups skip evaluation.

    Args:
        db: Active SQLAlchemy session for database operations.

    Returns:
        None. Hardware info persisted to database or skipped if exists.

    Note:
        Falls back to safe default values if hardware evaluation fails.
        Used by frontend to display system capabilities and recommend models.
    """
    persist_hw_infos = db.query(StaticHardwareInfo).first()
    if persist_hw_infos:
        return
    try:
        hw = get_hardware_eval_for_apple_silicon()
    except Exception as e:
        logger.warning(f"Hardware evaluation failed: {e}. Using fallback values.")
        hw = {
            "chip_model": "Unknown",
            "cpu_model": "Unknown CPU",
            "gpu_name": "Unknown GPU",
            "total_memory_gb": 8.0,
            "available_memory_gb": 4.0,
            "disk_total_gb": 100.0,
            "disk_available_gb": 50.0,
            "global_inference_score": 20.0,
            "global_inference_label": "Poor",
            "global_finetuning_score": 15.0,
            "global_finetuning_label": "Very Poor",
            "cpu_score": 30.0,
            "gpu_score": 20.0,
            "memory_score": 25.0,
            "mps_available": False,
            "is_apple_silicon": False
        }
    persist_hw_infos = StaticHardwareInfo(
        chip_model=hw.get("chip_model"),
        cpu_model=hw.get("cpu_model"),
        gpu_name=hw.get("gpu_name"),
        system_ram_gb=hw.get("total_memory_gb"),
        available_ram_gb=hw.get("available_memory_gb"),
        disk_total_gb=hw.get("disk_total_gb"),
        disk_avail_gb=hw.get("disk_available_gb"),
        gpu_cores=hw.get("gpu_cores"),
        estimated_gpu_tflops=hw.get("estimated_gpu_tflops"),
        memory_bandwidth_gbs=hw.get("memory_bandwidth_gbs"),
        neural_engine_tops=hw.get("neural_engine_tops"),
        cpu_performance_units=hw.get("cpu_performance_units"),
        architecture=hw.get("architecture"),
        is_apple_silicon=hw.get("is_apple_silicon", False),
        mps_available=hw.get("mps_available", False),
        unified_memory=hw.get("unified_memory", False),
        system_platform=hw.get("system_platform"),
        global_inference_score=hw.get("global_inference_score"),
        global_inference_label=hw.get("global_inference_label"),
        global_finetuning_score=hw.get("global_finetuning_score"),
        global_finetuning_label=hw.get("global_finetuning_label"),
        cpu_score=hw.get("cpu_score"),
        gpu_score=hw.get("gpu_score"),
        memory_score=hw.get("memory_score"),
        performance_breakdown=hw.get("performance_breakdown")
    )
    db.add(persist_hw_infos)
    db.commit()

def initialize_startup_variables(db: Session):
    """Initialize or refresh startup state variables.

    Creates StartupVariables record on first run. Used to track:
    - welcome_popup_has_already_displayed: First-run welcome screen flag

    Args:
        db: Active SQLAlchemy session for database operations.

    Returns:
        None. StartupVariables record created or refreshed.

    Note:
        Future startup flags (onboarding state, dismissed notifications)
        should be added as columns to StartupVariables entity.
    """
    variables = db.query(StartupVariables).first()
    if not variables:
        variables = StartupVariables(welcome_popup_has_already_displayed=False)
        db.add(variables)
        db.commit()
    else:
        db.refresh(variables)