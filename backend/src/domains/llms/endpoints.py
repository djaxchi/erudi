"""LLM model management API endpoints for browsing, downloading, and deleting models.

This module provides REST endpoints for:
- Listing available LLMs (all, local only, remote only)
- Fetching individual LLM details
- Downloading models from HuggingFace
- Deleting local models and freeing disk space
- Tracking download progress via background jobs
- Searching models by name

Model States:
    - local=0: Remote model (available on HuggingFace, not downloaded)
    - local=1: Local model (downloaded and ready for inference)
    - local=2: Downloading (background job in progress)

Architecture:
    LLM Lifecycle:
    ┌────────────────────────────────────────────────────────────┐
    │ GET /llms/remote                                           │
    │  └─> Browse available models from HuggingFace              │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ POST /llms/{llm_id}/download                               │
    │  1. Create local LLM record (local=2)                      │
    │  2. Create DownloadJob record                              │
    │  3. Start background download task                         │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ GET /llms/download_jobs/{job_id}                           │
    │  └─> Poll download progress (percentage, ETA)              │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ GET /llms/local                                            │
    │  └─> List downloaded models (local=1)                      │
    └────────────────────────────────────────────────────────────┘

Download Process:
    1. Fetch model from HuggingFace (snapshot_download)
    2. Quantize to engine-specific format (MLX 4-bit, GGUF, etc.)
    3. Save to data/models/{llm_id}/
    4. Update LLM record: local=1, link=local_path
    5. Mark DownloadJob as completed

Endpoints:
    - GET / → List all LLMs
    - GET /local → List local (downloaded) LLMs
    - GET /remote → List remote (HuggingFace) LLMs
    - GET /{llm_id} → Get LLM details
    - GET /search?name=<query> → Search LLMs by name
    - POST /{llm_id}/download → Start model download
    - DELETE /{llm_id} → Delete local model files
    - PUT /{llm_id} → Update LLM metadata
    - GET /download_jobs → List all download jobs
    - GET /download_jobs/{job_id} → Get download job status
    - DELETE /download_jobs/{job_id} → Cancel download job

Example:
    Download and use a model::

        # 1. List available remote models
        GET /erudi/llms/remote
        → [{"id": 42, "name": "Mistral-7B", "local": 0, ...}]

        # 2. Start download
        POST /erudi/llms/42/download
        → {"job_id": 123, "status": "running", "progress": 0.0}

        # 3. Poll progress
        GET /erudi/llms/download_jobs/123
        → {"job_id": 123, "status": "running", "progress": 45.2, "eta_seconds": 120}

        # 4. Wait for completion
        GET /erudi/llms/download_jobs/123
        → {"job_id": 123, "status": "completed", "progress": 100.0}

        # 5. Use model in conversation
        POST /erudi/conversations/
        {"llm_id": 42, ...}

Note:
    - Downloads run in background via FastAPI BackgroundTasks
    - Large models (7B+) take 5-30 minutes depending on connection
    - Quantization (MLX 4-bit) reduces size by ~75%
    - Disk space check performed before download

Warning:
    DELETE /{llm_id} permanently removes model files. Cannot be undone.
    Ensure model is not in use (check conversations) before deleting.
"""

import asyncio, os, shutil, asyncio
from typing import List
from datetime import datetime, timedelta

from fastapi import BackgroundTasks, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from src.database.core import get_db, SessionLocal

from src.entities.Llm import Llm
from src.entities.DownloadJob import DownloadJobModel
from src.domains.llms.schemas import LLMCreate, LLMResponse, DownloadJobResponse
from src.domains.llms.services import download_llm

from src.core.logging import logger

router = APIRouter(prefix="/llms", tags=["llms"])

@router.get("/", response_model=List[LLMResponse])
async def get_all_llms(db: Session = Depends(get_db)):
    """List all LLMs (local and remote).

    Returns:
        List[LLMResponse]: All LLM models with metadata.
    """
    llms = db.query(Llm).all()
    return llms

@router.get("/local", response_model=List[LLMResponse])
async def get_local_llms(db: Session = Depends(get_db)):
    """List only local (downloaded) LLMs ready for inference.

    Returns:
        List[LLMResponse]: LLMs with local=1.
    """
    llms = db.query(Llm).filter(Llm.local == 1).all()
    return llms

@router.get("/remote", response_model=List[LLMResponse])
async def get_remote_llms(db: Session = Depends(get_db)):
    """List only remote (HuggingFace) LLMs available for download.

    Returns:
        List[LLMResponse]: LLMs with local=0.
    """
    llms = db.query(Llm).filter(Llm.local == 0).all()
    return llms

@router.get("/{llm_id}", response_model=LLMResponse)
async def get_llm_by_id(llm_id: int, db: Session = Depends(get_db)):
    """Get LLM details by ID.

    Args:
        llm_id: ID of the LLM to retrieve.

    Returns:
        LLMResponse: LLM metadata.

    Raises:
        HTTPException: 404 if LLM not found.
    """
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    return llm

@router.put("/{llm_id}", response_model=LLMResponse)
async def update_llm(llm_id: int, llm: LLMCreate, db: Session = Depends(get_db)):
    """Update LLM metadata (name, description, etc.).

    Args:
        llm_id: ID of the LLM to update.
        llm: LLMCreate schema with new values.

    Returns:
        LLMResponse: Updated LLM.

    Raises:
        HTTPException: 404 if LLM not found.
    """
    db_llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not db_llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    for key, value in llm.dict().items():
        setattr(db_llm, key, value)
    db.commit()
    db.refresh(db_llm)
    return db_llm

@router.delete("/{llm_id}")
async def delete_llm(llm_id: int, db: Session = Depends(get_db)):
    """Delete local LLM and its files (permanent deletion).

    Args:
        llm_id: ID of the LLM to delete.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: 404 if LLM not found, 400 if currently downloading.

    Warning:
        Deletes model files from disk. Cannot be undone.
    """
    db_llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not db_llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    if db_llm.local == 2:
        raise HTTPException(status_code=400, detail="LLM is currently downloading")
    if db_llm.link and os.path.exists(db_llm.link):
        shutil.rmtree(db_llm.link, ignore_errors=True)
    db.delete(db_llm)
    db.commit()
    return {"message": "LLM deleted successfully"}

@router.get("/search", response_model=List[LLMResponse])
async def search_llms(name: str, db: Session = Depends(get_db)):
    """Search LLMs by name (case-insensitive partial match).

    Args:
        name: Search query string.

    Returns:
        List[LLMResponse]: Matching LLMs.
    """
    llms = db.query(Llm).filter(Llm.name.ilike(f"%{name}%")).all()
    return llms


@router.post(
    "/{llm_id}/download",
    response_model=DownloadJobResponse,
    status_code=200,
)
async def download_llm_route(
    llm_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start background download of LLM from HuggingFace.

    Creates a DownloadJob and runs download in background. Model is quantized
    during download (MLX 4-bit for Mac Silicon, GGUF for others).

    Args:
        llm_id: ID of the remote LLM to download.
        background_tasks: FastAPI background tasks manager.

    Returns:
        DownloadJobResponse: Job record with job_id, status, progress.

    Raises:
        HTTPException: 404 if LLM not found.

    Note:
        Download progress can be polled via GET /download_jobs/{job_id}.
        Large models (7B+) take 5-30 minutes.
    """
    """
    Start a new DownloadJobModel for the given LLM. Returns the DownloadJobModel record.
    """
    remote_llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not remote_llm:
        raise HTTPException(status_code=404, detail="LLM not found")

    # Create new instance of Llm
    local_llm = Llm(
        name=remote_llm.name,
        local=2,  # 2 means downloading
        type=remote_llm.type,
        description=remote_llm.description,
        model_metadata=remote_llm.model_metadata,  # Copy metadata from remote model
        quantized=remote_llm.quantized,  # Copy quantized flag from remote model
        param_size=remote_llm.param_size,  # Copy parameter size from remote model
    )
    try:
        db.add(local_llm)
        db.commit()
        db.refresh(local_llm)
    except:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create local LLM entry")
    
    try:
        temp_path = f"./data/models/temp_{local_llm.id}"
        final_path = f"./data/models/{local_llm.id}"
        if os.path.exists(temp_path):
            raise
        if os.path.exists(final_path):
            raise
        local_llm.link = final_path
        db.commit()
        logger.info(f"Created local LLM entry: {local_llm.name} - {local_llm.link}")
    except:
        db.delete(local_llm)
        raise HTTPException(status_code=500, detail="Failed to create local LLM entry")
    
    # Create persistent DownloadJobModel
    job = DownloadJobModel(
        remote_model_id=llm_id,
        local_model_id=local_llm.id,
        remote_model_link=remote_llm.link,
        temp_local_model_link=local_llm.link,
        final_local_model_link=final_path,
        status="pending",
        total_bytes=0.0,
        progress=0.0,
    )
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create DownloadJobModel")

    def _download_task(model_link: str, model_id: int, temp_save_dir: str, final_save_dir: str, job_id: int):
        try:
            # mark RUNNING
            session = SessionLocal()
            dj = session.query(DownloadJobModel).get(job_id)
            dj.status = "running"
            dj.updated_at = datetime.now()
            session.commit()
            session.close()

            # call the downloader (it will spawn its own updater thread)
            
            asyncio.run(
                download_llm(
                    model_link=model_link,
                    model_id=model_id,
                    temp_save_dir=temp_save_dir,
                    final_save_dir=final_save_dir,
                    job_id=job_id,
                )
            )
        except Exception as e:
            session = SessionLocal()
            dj = session.query(DownloadJobModel).get(job_id)
            dj.status = "failed"
            dj.error_message = str(e)
            dj.updated_at = datetime.now()
            session.commit()
            session.close()

    # 2) enqueue background
    background_tasks.add_task(
        _download_task,
        remote_llm.link,
        local_llm.id,
        temp_path,
        final_path,
        job.id,
    )

    # 3) immediately return the DB row
    return job


@router.post(
    "/downloads/{job_id}/cancel",
    status_code=200,
)
def cancel_download(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Cancel an active download job and cleanup partial files.

    Args:
        job_id: ID of the download job to cancel.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: 404 if job not found, 400 if already completed/failed.

    Note:
        Deletes temp files and marks LLM as failed. Cannot cancel completed jobs.
    """
    """
    Cancel a download by its job_id.
    """
    job = db.query(DownloadJobModel).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    if job.status in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or failed jobs")
    llm = db.query(Llm).get(job.local_model_id)
    if not llm:
        raise HTTPException(status_code=404, detail="Local model not found")
    if llm.local != 2:
        raise HTTPException(status_code=400, detail="Download ended, cannot be cancelled. Please delete the model.")
    
    # Mark the job as cancelled
    job.status = "cancelled"
    job.updated_at = datetime.now()
    db.commit()

    # Clean up local model if it exists
    if job.temp_local_model_link and job.temp_local_model_link != "":
        if os.path.exists(job.temp_local_model_link):
            shutil.rmtree(job.temp_local_model_link, ignore_errors=True)
        if "temp" not in job.temp_local_model_link and os.path.exists("./data/models/temp_"+str(job.local_model_id)):
            shutil.rmtree("./data/models/temp_"+str(job.local_model_id), ignore_errors=True)
        job.temp_local_model_link = ""
    if job.final_local_model_link:
        if os.path.exists(job.final_local_model_link) and job.final_local_model_link!= "":
            shutil.rmtree(job.final_local_model_link, ignore_errors=True)
        job.final_local_model_link = ""
    job.local_model_id = -1
    db.delete(llm)

    db.commit()
    return {"message": "Download job cancelled successfully"}


@router.get(
    "/downloads/{job_id}/status",
    response_model=DownloadJobResponse,
    status_code=200,
)
def get_download_status_by_jobId(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Get download job status by ID with automatic cleanup for failed/cancelled jobs.

    Polls the download job status and performs cleanup operations for terminal states
    (failed/cancelled/completed). Failed/cancelled jobs delete the temp LLM entry and
    clean up temporary files. Completed jobs mark the LLM as local=1 (ready).

    Args:
        job_id: The database ID of the download job to query.
        db: Database session injected by FastAPI.

    Returns:
        DownloadJobResponse: Download job with current status, progress, ETA, and file paths.

    Raises:
        HTTPException: 404 if job_id not found or associated LLM missing.

    Example:
        GET /llms/downloads/42/status
        Response: {"id": 42, "status": "running", "progress": 65.0, "eta_seconds": 120, ...}
    """
    job = db.query(DownloadJobModel).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    
    if job.status == "failed" or job.status == "cancelled":
        llm = db.query(Llm).filter(Llm.id == job.local_model_id).first()
        if not llm:
            raise HTTPException(status_code=404, detail="LLM not found")
        db.delete(llm)
        job.local_model_id = -1
        if job.temp_local_model_link and job.temp_local_model_link != "":
            if os.path.exists(job.temp_local_model_link):
                shutil.rmtree(job.temp_local_model_link, ignore_errors=True)
            if "temp" not in job.temp_local_model_link and os.path.exists("./data/models/temp_"+str(job.local_model_id)):
                shutil.rmtree("./data/models/temp_"+str(job.local_model_id), ignore_errors=True)
            job.temp_local_model_link = ""
        if job.final_local_model_link and job.final_local_model_link != "":
            if os.path.exists(job.final_local_model_link):
                shutil.rmtree(job.final_local_model_link, ignore_errors=True)
            job.final_local_model_link = ""
        job.updated_at = datetime.now()
        db.commit()
        db.refresh(job)
    elif job.status == "completed":
        llm = db.query(Llm).filter(Llm.id == job.local_model_id).first()
        if not llm:
            raise HTTPException(status_code=404, detail="LLM not found")
        llm.local = 1
        db.commit()
        db.refresh(llm)
    return job


@router.get(
    "/downloads/status",
    response_model=DownloadJobResponse,
    status_code=200,
)
def get_download_status_without_jobId(
    db: Session = Depends(get_db),
):
    """Get most recent active download job (for single-download UI polling).

    Finds the most recently updated download job that is still running/pending within
    the last 60 seconds. Useful for UIs that only support one active download at a time
    and need to poll without tracking job IDs. Performs same cleanup as get_by_id.

    Args:
        db: Database session injected by FastAPI.

    Returns:
        DownloadJobResponse: The most recent active job with status and progress.

    Raises:
        HTTPException: 404 if no active job found in last 60 seconds, or LLM missing.

    Example:
        GET /llms/downloads/status
        Response: {"id": 42, "status": "running", "progress": 65.0, ...}
    """
    sixty_seconds_ago = datetime.now() - timedelta(seconds=60)
    job = db.query(DownloadJobModel)\
           .filter(DownloadJobModel.status.in_(["running", "pending"]))\
           .filter(DownloadJobModel.updated_at >= sixty_seconds_ago)\
           .order_by(DownloadJobModel.updated_at.desc())\
           .first()
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    
    if job.status == "failed":
        llm = db.query(Llm).filter(Llm.id == job.local_model_id).first()
        if not llm:
            raise HTTPException(status_code=404, detail="LLM not found")
        db.delete(llm)
        job.local_model_id = -1
        if job.temp_local_model_link and job.temp_local_model_link != "":
            if os.path.exists(job.temp_local_model_link):
                shutil.rmtree(job.temp_local_model_link, ignore_errors=True)
            if "temp" not in job.temp_local_model_link and os.path.exists("./data/models/temp_"+str(job.local_model_id)):
                shutil.rmtree("./data/models/temp_"+str(job.local_model_id), ignore_errors=True)
            job.temp_local_model_link = ""
        if job.final_local_model_link and job.final_local_model_link != "":
            if os.path.exists(job.final_local_model_link):
                shutil.rmtree(job.final_local_model_link, ignore_errors=True)
            job.final_local_model_link = ""
        job.updated_at = datetime.now()
        db.commit()
        db.refresh(job)
    elif job.status == "completed":
        llm = db.query(Llm).filter(Llm.id == job.local_model_id).first()
        if not llm:
            raise HTTPException(status_code=404, detail="LLM not found")
        llm.local = 1
        db.commit()
        db.refresh(llm)
    return job