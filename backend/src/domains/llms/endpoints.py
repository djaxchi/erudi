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
    3. Save to config.LLM_DIR/{llm_id}/
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

import asyncio, os, shutil
from typing import List
from datetime import datetime, timedelta

from fastapi import BackgroundTasks, Depends, HTTPException, APIRouter, status as http_status
from sqlalchemy.orm import Session
from src.database.core import get_db, SessionLocal

from src.entities.Llm import Llm
from src.entities.DownloadJob import DownloadJobModel
from src.domains.llms.schemas import LLMCreate, LLMResponse, DownloadJobResponse
from src.domains.llms.services import download_llm
from src.domains.llms.repository import Llm_Repository, Download_Job_Repository

from src.core.logging import logger
from src.core import config
from src.core.exceptions import (
    ModelNotFoundException,
    DatabaseException,
    InvalidInputException,
    StateConflictException,
    FileSystemException,
    DownloadJobNotFoundException,
)

router = APIRouter(prefix="/llms", tags=["llms"])


# ============ Dependency Injection ============

def get_llm_repository(db: Session = Depends(get_db)) -> Llm_Repository:
    """Dependency injection for Llm_Repository.

    Args:
        db: Database session from FastAPI.

    Returns:
        Llm_Repository: Repository instance with injected session.
    """
    return Llm_Repository(db)


def get_download_job_repository(db: Session = Depends(get_db)) -> Download_Job_Repository:
    """Dependency injection for Download_Job_Repository.

    Args:
        db: Database session from FastAPI.

    Returns:
        Download_Job_Repository: Repository instance with injected session.
    """
    return Download_Job_Repository(db)


# ============ LLM CRUD Endpoints ============

# ============ LLM CRUD Endpoints ============

@router.get("/", response_model=List[LLMResponse])
async def get_all_llms(llm_repo: Llm_Repository = Depends(get_llm_repository)):
    """List all LLMs (local and remote).

    Args:
        llm_repo: Injected LLM repository.

    Returns:
        List[LLMResponse]: All LLM models with metadata.
    """
    # Read-only operation, no commit needed
    llms = llm_repo.get_all()
    return llms


@router.get("/local", response_model=List[LLMResponse])
async def get_local_llms(llm_repo: Llm_Repository = Depends(get_llm_repository)):
    """List only local (downloaded) LLMs ready for inference.

    Args:
        llm_repo: Injected LLM repository.

    Returns:
        List[LLMResponse]: LLMs with local=1.
    """
    # Read-only operation, no commit needed
    llms = llm_repo.get_all_local()
    return llms


@router.get("/remote", response_model=List[LLMResponse])
async def get_remote_llms(llm_repo: Llm_Repository = Depends(get_llm_repository)):
    """List only remote (HuggingFace) LLMs available for download.

    Args:
        llm_repo: Injected LLM repository.

    Returns:
        List[LLMResponse]: LLMs with local=0.
    """
    # Read-only operation, no commit needed
    llms = llm_repo.get_all_remote()
    return llms


@router.get("/search", response_model=List[LLMResponse])
async def search_llms(name: str, llm_repo: Llm_Repository = Depends(get_llm_repository)):
    """Search LLMs by name (case-insensitive partial match).

    Args:
        name: Search query string.
        llm_repo: Injected LLM repository.

    Returns:
        List[LLMResponse]: Matching LLMs.
    """
    # Read-only operation, no commit needed
    llms = llm_repo.search_by_name(name)
    return llms


@router.get("/{llm_id}", response_model=LLMResponse)
async def get_llm_by_id(
    llm_id: int,
    llm_repo: Llm_Repository = Depends(get_llm_repository)
):
    """Get LLM details by ID.

    Args:
        llm_id: ID of the LLM to retrieve.
        llm_repo: Injected LLM repository.

    Returns:
        LLMResponse: LLM metadata.

    Raises:
        ModelNotFoundException: If LLM not found.
    """
    # Read-only operation, no commit needed
    llm = llm_repo.get_by_id(llm_id)
    if not llm:
        raise ModelNotFoundException(f"LLM {llm_id}")
    return llm

@router.put("/{llm_id}", response_model=LLMResponse)
async def update_llm(
    llm_id: int,
    llm_data: LLMCreate,
    llm_repo: Llm_Repository = Depends(get_llm_repository),
    db: Session = Depends(get_db),
):
    """Update LLM metadata (name, description, etc.).

    Args:
        llm_id: ID of the LLM to update.
        llm_data: LLMCreate schema with new values.
        llm_repo: Injected LLM repository.
        db: Database session for transaction control.

    Returns:
        LLMResponse: Updated LLM.

    Raises:
        ModelNotFoundException: If LLM not found.
        DatabaseException: If update fails.
    """
    try:
        llm = llm_repo.get_by_id(llm_id)
        if not llm:
            raise ModelNotFoundException(f"LLM {llm_id}")
        
        # Update fields from request
        updated_llm = llm_repo.update(llm, **llm_data.dict())
        db.commit()
        return updated_llm
    except ModelNotFoundException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to update LLM {llm_id}: {e}")
        raise DatabaseException(
            "Failed to update LLM",
            trace=str(e)
        )

@router.delete("/{llm_id}")
async def delete_llm(
    llm_id: int,
    llm_repo: Llm_Repository = Depends(get_llm_repository),
    db: Session = Depends(get_db),
):
    """Delete local LLM and its files (permanent deletion).

    Args:
        llm_id: ID of the LLM to delete.
        llm_repo: Injected LLM repository.
        db: Database session for transaction control.

    Returns:
        dict: Success message.

    Raises:
        ModelNotFoundException: If LLM not found.
        StateConflictException: If currently downloading.
        DatabaseException: If deletion fails.

    Warning:
        Deletes model files from disk. Cannot be undone.
    """
    try:
        llm = llm_repo.get_by_id(llm_id)
        if not llm:
            raise ModelNotFoundException(f"LLM {llm_id}")
        
        if llm.local == 2:
            raise StateConflictException("Cannot delete LLM while downloading")
        
        # Delete files from disk if they exist
        if llm.link and os.path.exists(llm.link):
            shutil.rmtree(llm.link, ignore_errors=True)
            logger.info(f"Deleted model files: {llm.link}")
            
            # Check and delete residual temp files (e.g., temp_36 for llm.link = data/models/36)
            temp_path = config.LLM_DIR / f"temp_{llm.id}"
            if os.path.exists(str(temp_path)):
                shutil.rmtree(str(temp_path), ignore_errors=True)
                logger.warning(f"Deleting residual temp files associated to llm: {temp_path}")
        
        # Delete database record
        llm_repo.delete(llm)
        db.commit()
        
        return {"message": "LLM deleted successfully"}
        
    except (ModelNotFoundException, StateConflictException):
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to delete LLM {llm_id}: {e}")
        raise DatabaseException(
            "Failed to delete LLM",
            trace=str(e)
        )


# ============ Download Management Endpoints ============

@router.post(
    "/{llm_id}/download",
    response_model=DownloadJobResponse,
    status_code=http_status.HTTP_200_OK,
)
async def download_llm_route(
    llm_id: int,
    background_tasks: BackgroundTasks,
    llm_repo: Llm_Repository = Depends(get_llm_repository),
    job_repo: Download_Job_Repository = Depends(get_download_job_repository),
    db: Session = Depends(get_db),
):
    """Start background download of LLM from HuggingFace.

    Creates a DownloadJob and runs download in background. Model is quantized
    during download (MLX 4-bit for Mac Silicon, GGUF for others).

    Args:
        llm_id: ID of the remote LLM to download.
        background_tasks: FastAPI background tasks manager.
        llm_repo: Injected LLM repository.
        job_repo: Injected download job repository.
        db: Database session for transaction control.

    Returns:
        DownloadJobResponse: Job record with job_id, status, progress.

    Raises:
        HTTPException: 404 if LLM not found, 500 if paths already exist.

    Note:
        Download progress can be polled via GET /downloads/{job_id}/status.
        Large models (7B+) take 5-30 minutes.
    """
    try:
        # Get remote LLM metadata
        remote_llm = llm_repo.get_by_id(llm_id)
        if not remote_llm:
            raise ModelNotFoundException(f"LLM {llm_id}")

        # Create temp LLM entry (local=2 means "downloading")
        local_llm = llm_repo.create(
            name=remote_llm.name,
            local=2,
            type=remote_llm.type,
            description=remote_llm.description,
            model_metadata=remote_llm.model_metadata,
            quantized=remote_llm.quantized,
            param_size=remote_llm.param_size,
        )
        
        # Define paths and check availability
        temp_path = config.LLM_DIR / f"temp_{local_llm.id}"
        final_path = config.LLM_DIR / str(local_llm.id)
        
        if temp_path.exists() or final_path.exists():
            llm_repo.delete(local_llm)
            db.rollback()
            raise FileSystemException(
                "Model path already exists - delete existing files first"
            )
        
        # Update local LLM with final path
        llm_repo.update(local_llm, link=str(final_path))
        db.commit()
        logger.info(f"Created local LLM entry {local_llm.id}: {local_llm.name} -> {final_path}")

        # Create download job
        job = job_repo.create(
            remote_model_id=str(llm_id),
            local_model_id=local_llm.id,
            remote_model_link=remote_llm.link,
            temp_local_model_link=str(temp_path),
            final_local_model_link=str(final_path),
            status="pending",
        )
        db.commit()
        logger.info(f"Created download job {job.id} for model {local_llm.name}")

        # Background task function
        def _download_task(
            model_link: str,
            model_id: int,
            temp_save_dir: str,
            final_save_dir: str,
            job_id: int
        ):
            """Background download task with error handling."""
            session = SessionLocal()
            try:
                # Mark job as running
                job_obj = session.query(DownloadJobModel).get(job_id)
                job_obj.status = "running"
                job_obj.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"Started download job {job_id}")

                # Run download (spawns its own progress updater thread)
                asyncio.run(
                    download_llm(
                        model_link=model_link,
                        model_id=model_id,
                        temp_save_dir=temp_save_dir,
                        final_save_dir=final_save_dir,
                        job_id=job_id,
                    )
                )
                logger.info(f"Download job {job_id} completed successfully")
                
            except Exception as e:
                logger.exception(f"Download job {job_id} failed: {e}")
                job_obj = session.query(DownloadJobModel).get(job_id)
                job_obj.status = "failed"
                job_obj.error_message = str(e)
                job_obj.updated_at = datetime.utcnow()
                session.commit()
            finally:
                session.close()

        # Enqueue background task
        background_tasks.add_task(
            _download_task,
            remote_llm.link,
            local_llm.id,
            temp_path,
            final_path,
            job.id,
        )

        return job

    except (ModelNotFoundException, InvalidInputException):
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to initiate download for LLM {llm_id}: {e}")
        raise DatabaseException(
            "Failed to start download",
            trace=str(e)
        )


@router.post(
    "/downloads/{job_id}/cancel",
    status_code=200,
)
async def cancel_download(
    job_id: int,
    llm_repo: Llm_Repository = Depends(get_llm_repository),
    job_repo: Download_Job_Repository = Depends(get_download_job_repository),
    db: Session = Depends(get_db),
):
    """Cancel an active download job and cleanup partial files.

    Args:
        job_id: ID of the download job to cancel.
        llm_repo: Injected LLM repository.
        job_repo: Injected download job repository.
        db: Database session for transaction control.

    Returns:
        dict: Success message with cancellation status.

    Raises:
        DownloadJobNotFoundException: If job not found.
        ModelNotFoundException: If LLM not found.
        InvalidInputException: If already completed/failed or not in download state.
        DatabaseException: If cancellation fails.

    Note:
        - Signals download process to stop via DownloadTracker
        - Deletes temp files and model entry from database
        - Cannot cancel completed jobs
        - Transaction ensures atomic cleanup
    """
    try:
        # Get job and validate state
        job = job_repo.get_by_id(job_id)
        if not job:
            raise DownloadJobNotFoundException(job_id)
        if job.status in ["completed", "failed", "cancelled"]:
            raise StateConflictException(
                "Cannot cancel a job that is already completed, failed, or cancelled"
            )
        
        # Get associated LLM and validate state
        llm = llm_repo.get_by_id(job.local_model_id)
        if not llm:
            raise ModelNotFoundException(f"LLM {job.local_model_id}")
        if llm.local != 2:
            raise InvalidInputException("Download ended - cannot be cancelled, please delete the model")
        
        # Signal cancellation to download process
        job_repo.update_status(job, "cancelling")
        db.commit()
        
        # Get download tracker from active tasks
        from src.domains.llms.services import get_active_download_tracker
        tracker = get_active_download_tracker(job_id)
        if tracker:
            tracker.cancel()
            logger.info(f"Signaled cancellation for download job {job_id}")
        else:
            logger.warning(f"No active download tracker found for job {job_id}, proceeding with cleanup")

        # Clean up immediately in both cases
        job_repo.update_status(job, "cancelled")
        job_repo.cleanup_job_files(job)
        llm_repo.delete(llm)
        db.commit()
            
        return {
            "message": "Download cancellation initiated",
            "job_id": job_id,
            "status": "cancelling"
        }
    
    except (DownloadJobNotFoundException, ModelNotFoundException, InvalidInputException, StateConflictException):
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to cancel download job {job_id}: {e}")
        raise DatabaseException(
            "Failed to cancel download",
            trace=str(e)
        )


@router.get(
    "/downloads/{job_id}/status",
    response_model=DownloadJobResponse,
    status_code=200,
)
def get_download_status_by_jobId(
    job_id: int,
    llm_repo: Llm_Repository = Depends(get_llm_repository),
    job_repo: Download_Job_Repository = Depends(get_download_job_repository),
    db: Session = Depends(get_db),
):
    """Get download job status by ID with automatic cleanup for failed/cancelled jobs.

    Polls the download job status and performs cleanup operations for terminal states
    (failed/cancelled/completed). Failed/cancelled jobs delete the temp LLM entry and
    clean up temporary files. Completed jobs mark the LLM as local=1 (ready).

    Args:
        job_id: The database ID of the download job to query.
        llm_repo: Injected LLM repository.
        job_repo: Injected download job repository.
        db: Database session for transaction control.

    Returns:
        DownloadJobResponse: Download job with current status, progress, ETA, and file paths.

    Raises:
        DownloadJobNotFoundException: If job_id not found.
        ModelNotFoundException: If associated LLM missing.
        DatabaseException: If status fetch fails.

    Example:
        GET /llms/downloads/42/status
        Response: {"id": 42, "status": "running", "progress": 65.0, "eta_seconds": 120, ...}
    """
    try:
        job = job_repo.get_by_id(job_id)
        if not job:
            raise DownloadJobNotFoundException(job_id)
        
        # Handle failed/cancelled jobs: cleanup temp files and LLM entry
        if job.status in ["failed", "cancelled"]:
            llm = llm_repo.get_by_id(job.local_model_id)
            if not llm:
                raise ModelNotFoundException(f"LLM {job.local_model_id}")
            
            # Delete temp LLM entry
            llm_repo.delete(llm)
            
            # Clean up temp files using repository method
            job_repo.cleanup_job_files(job)
            
            db.commit()
            db.refresh(job)
            logger.info(f"Cleaned up {job.status} download job {job_id}")
        
        # Handle completed jobs: mark LLM as ready
        elif job.status == "completed":
            llm = llm_repo.get_by_id(job.local_model_id)
            if not llm:
                raise ModelNotFoundException(f"LLM {job.local_model_id}")
            llm_repo.update(llm, local=1)
            db.commit()
            db.refresh(llm)
            logger.info(f"Marked LLM {llm.id} as ready (download job {job_id} completed)")
        
        return job
    
    except (DownloadJobNotFoundException, ModelNotFoundException):
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to get download status for job {job_id}: {e}")
        raise DatabaseException(
            "Failed to get download status",
            trace=str(e)
        )


@router.get(
    "/downloads/status",
    response_model=DownloadJobResponse,
    status_code=200,
)
def get_download_status_without_jobId(
    llm_repo: Llm_Repository = Depends(get_llm_repository),
    job_repo: Download_Job_Repository = Depends(get_download_job_repository),
    db: Session = Depends(get_db),
):
    """Get most recent active download job (for single-download UI polling).

    Finds the most recently updated download job that is still running/pending within
    the last 60 seconds. Useful for UIs that only support one active download at a time
    and need to poll without tracking job IDs. Performs same cleanup as get_by_id.

    Args:
        llm_repo: Injected LLM repository.
        job_repo: Injected download job repository.
        db: Database session for transaction control.

    Returns:
        DownloadJobResponse: The most recent active job with status and progress.

    Raises:
        DownloadJobNotFoundException: If no active job found in last 60 seconds.
        ModelNotFoundException: If LLM missing.
        DatabaseException: If status fetch fails.

    Example:
        GET /llms/downloads/status
        Response: {"id": 42, "status": "running", "progress": 65.0, ...}
    """
    try:
        # Get most recent active job
        job = job_repo.get_most_recent_active()
        if not job:
            raise DownloadJobNotFoundException("recent active")
        
        # Handle failed jobs: cleanup temp files and LLM entry
        if job.status == "failed":
            llm = llm_repo.get_by_id(job.local_model_id)
            if not llm:
                raise ModelNotFoundException(f"LLM {job.local_model_id}")
            
            # Delete temp LLM entry
            llm_repo.delete(llm)
            
            # Clean up temp files using repository method
            job_repo.cleanup_job_files(job)
            
            db.commit()
            db.refresh(job)
            logger.info(f"Cleaned up failed download job {job.id}")
        
        # Handle completed jobs: mark LLM as ready
        elif job.status == "completed":
            llm = llm_repo.get_by_id(job.local_model_id)
            if not llm:
                raise ModelNotFoundException(f"LLM {job.local_model_id}")
            llm_repo.update(llm, local=1)
            db.commit()
            db.refresh(llm)
            logger.info(f"Marked LLM {llm.id} as ready (download job {job.id} completed)")
        
        return job
    
    except (DownloadJobNotFoundException, ModelNotFoundException):
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to get recent download status: {e}")
        raise DatabaseException(
            "Failed to get download status",
            trace=str(e)
        )