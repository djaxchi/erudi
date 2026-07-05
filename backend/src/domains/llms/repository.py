"""Data access layer for LLM and DownloadJob entities.

This module provides repository classes following the Repository pattern for database
operations on LLMs and download jobs. Repositories encapsulate all SQLAlchemy queries
and database interactions, keeping the service and endpoint layers clean.

Architecture:
    - Llm_Repository: CRUD operations for LLM catalog entries.
    - Download_Job_Repository: CRUD operations for download job tracking.
    - update_db_with_progress: Background thread function for polling download progress.

Repository Pattern Benefits:
    - Single source of truth for data access logic.
    - Easy to mock for testing.
    - Clear separation between business logic (services) and data access.
    - Consistent error handling and logging.

Example:
    from src.domains.llms.repository import Llm_Repository, Download_Job_Repository

    # In endpoint or service
    llm_repo = Llm_Repository(db)
    llm = llm_repo.get_by_id(42)
"""
import os
import shutil
import time
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from src.database.core import SessionLocal
from src.entities.Llm import Llm
from src.entities.DownloadJob import DownloadJobModel
from src.core.logging import logger
from src.core import config


class Llm_Repository:
    """Repository for LLM entity database operations.

    Handles all CRUD operations and queries for the LLM catalog, including filtering
    by download state (local/remote) and search functionality.

    Attributes:
        db: SQLAlchemy database session (injected by FastAPI).

    Example:
        >>> llm_repo = Llm_Repository(db)
        >>> local_llms = llm_repo.get_all_local()
        >>> llm = llm_repo.create(name="Llama-3-8B", link="meta-llama/...", local=0)
    """

    def __init__(self, db: Session):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db
        logger.debug("Initializing Llm_Repository")

    def get_all(self) -> List[Llm]:
        """Retrieve all LLMs (local and remote).

        Returns:
            List[Llm]: All LLM records ordered by ID.
        """
        logger.debug("Retrieving all LLMs")
        return self.db.query(Llm).order_by(Llm.id).all()

    def get_all_local(self) -> List[Llm]:
        """Retrieve only local (downloaded) LLMs ready for inference.

        Returns:
            List[Llm]: LLMs with local=1, ordered by ID.
        """
        logger.debug("Retrieving local LLMs")
        return self.db.query(Llm).filter(Llm.local == 1).order_by(Llm.id).all()

    def get_all_remote(self) -> List[Llm]:
        """Retrieve only remote (HuggingFace) LLMs available for download.

        Returns:
            List[Llm]: LLMs with local=0, ordered by ID.
        """
        logger.debug("Retrieving remote LLMs")
        return self.db.query(Llm).filter(Llm.local == 0).order_by(Llm.id).all()

    def get_by_id(self, llm_id: int) -> Optional[Llm]:
        """Retrieve LLM by primary key.

        Args:
            llm_id: ID of the LLM to retrieve.

        Returns:
            Llm if found, None otherwise.
        """
        logger.debug(f"Retrieving LLM by ID: {llm_id}")
        return self.db.query(Llm).filter(Llm.id == llm_id).first()

    def search_by_name(self, name: str) -> List[Llm]:
        """Search LLMs by name (case-insensitive partial match).

        Args:
            name: Search query string.

        Returns:
            List[Llm]: Matching LLMs ordered by relevance.
        """
        logger.debug(f"Searching LLMs by name: {name}")
        return self.db.query(Llm).filter(Llm.name.ilike(f"%{name}%")).order_by(Llm.id).all()

    def create(
        self,
        name: str,
        local: int,
        type: str,
        description: Optional[str] = None,
        model_metadata: Optional[str] = None,
        quantized: bool = False,
        param_size: float = 4.0,
        link: Optional[str] = None,
        category: str = "general",
    ) -> Llm:
        """Create a new LLM catalog entry.

        Args:
            name: Human-readable model name.
            local: Download state (0=remote, 1=local, 2=downloading).
            type: Model family (e.g., "llama", "qwen").
            description: Optional model description.
            model_metadata: Optional JSON metadata string.
            quantized: Quantization state (False=not quantized, True=pre-quantized).
            param_size: Model size in billions of parameters.
            link: HuggingFace repo ID or local path.

        Returns:
            Llm: Created LLM entity (not yet committed, use flush()).
        """
        logger.info(f"Creating LLM: {name} (local={local})")
        llm = Llm(
            name=name,
            local=local,
            type=type,
            description=description,
            model_metadata=model_metadata,
            quantized=quantized,
            param_size=param_size,
            link=link,
            category=category,
        )
        self.db.add(llm)
        self.db.flush()
        self.db.refresh(llm)
        logger.info(f"Created LLM {llm.id}: {llm.name}")
        return llm

    def update(self, llm: Llm, **kwargs) -> Llm:
        """Update LLM fields (partial update).

        Args:
            llm: LLM entity to update.
            **kwargs: Fields to update (e.g., name="New Name", local=1).

        Returns:
            Llm: Updated LLM entity (not yet committed, use flush()).
        """
        logger.info(f"Updating LLM {llm.id}: {kwargs}")
        for key, value in kwargs.items():
            if hasattr(llm, key):
                setattr(llm, key, value)
        self.db.flush()
        self.db.refresh(llm)
        return llm

    def delete(self, llm: Llm) -> None:
        """Delete LLM entity and optionally clean up local files.

        Args:
            llm: LLM entity to delete.

        Note:
            Does not commit. Caller must handle db.commit() and file cleanup.
        """
        logger.info(f"Deleting LLM {llm.id}: {llm.name}")
        
        self.db.delete(llm)
        self.db.flush()


class Download_Job_Repository:
    """Repository for DownloadJob entity database operations.

    Handles all CRUD operations and queries for download job tracking, including
    status updates, progress monitoring, and cleanup operations.

    Attributes:
        db: SQLAlchemy database session (injected by FastAPI).

    Example:
        >>> job_repo = Download_Job_Repository(db)
        >>> job = job_repo.create(remote_model_id="meta-llama/...", status="pending")
        >>> job_repo.update_progress(job, progress=50.0, eta_seconds=120.0)
    """

    def __init__(self, db: Session):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db
        logger.debug("Initializing Download_Job_Repository")

    def get_by_id(self, job_id: int) -> Optional[DownloadJobModel]:
        """Retrieve download job by primary key.

        Args:
            job_id: ID of the download job.

        Returns:
            DownloadJobModel if found, None otherwise.
        """
        logger.debug(f"Retrieving download job by ID: {job_id}")
        return self.db.query(DownloadJobModel).filter(DownloadJobModel.id == job_id).first()

    def get_most_recent_active(self, max_age_seconds: int = 60) -> Optional[DownloadJobModel]:
        """Retrieve most recent active download job (for single-download UI polling).

        Finds the most recently updated job with status "running" or "pending" within
        the specified time window.

        Args:
            max_age_seconds: Maximum age in seconds (default 60).

        Returns:
            DownloadJobModel if found, None otherwise.
        """
        logger.debug(f"Retrieving most recent active job (max age: {max_age_seconds}s)")
        cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
        
        return (
            self.db.query(DownloadJobModel)
            .filter(DownloadJobModel.status.in_(["running", "pending"]))
            .filter(DownloadJobModel.updated_at >= cutoff)
            .order_by(DownloadJobModel.updated_at.desc())
            .first()
        )

    def create(
        self,
        remote_model_id: str,
        local_model_id: int,
        remote_model_link: str,
        temp_local_model_link: str,
        final_local_model_link: str,
        status: str = "pending",
    ) -> DownloadJobModel:
        """Create a new download job record.

        Args:
            remote_model_id: HuggingFace repo ID.
            local_model_id: Database ID of temp LLM entry.
            remote_model_link: HuggingFace URL.
            temp_local_model_link: Temp directory path.
            final_local_model_link: Final directory path.
            status: Initial job status (default "pending").

        Returns:
            DownloadJobModel: Created job entity (not yet committed, use flush()).
        """
        logger.info(f"Creating download job for model: {remote_model_id}")
        job = DownloadJobModel(
            remote_model_id=remote_model_id,
            local_model_id=local_model_id,
            remote_model_link=remote_model_link,
            temp_local_model_link=temp_local_model_link,
            final_local_model_link=final_local_model_link,
            status=status,
            total_bytes=0.0,
            progress=0.0,
        )
        self.db.add(job)
        self.db.flush()
        self.db.refresh(job)
        logger.info(f"Created download job {job.id}")
        return job

    def update_status(self, job: DownloadJobModel, status: str, error_message: Optional[str] = None) -> None:
        """Update download job status and optionally set error message.

        Args:
            job: Download job entity to update.
            status: New status (e.g., "running", "completed", "failed").
            error_message: Optional error message if status="failed".

        Note:
            Does not commit. Caller must handle db.commit().
        """
        logger.info(f"Updating job {job.id} status: {status}")
        job.status = status
        if error_message:
            job.error_message = error_message
        job.updated_at = datetime.utcnow()
        self.db.flush()

    def update_progress(
        self,
        job: DownloadJobModel,
        total_bytes: Optional[float] = None,
        progress: Optional[float] = None,
        elapsed_seconds: Optional[float] = None,
        eta_seconds: Optional[float] = None,
    ) -> None:
        """Update download job progress metrics.

        Args:
            job: Download job entity to update.
            total_bytes: Total download size in bytes.
            progress: Progress percentage (0.0-100.0).
            elapsed_seconds: Total elapsed time in seconds.
            eta_seconds: Estimated time remaining in seconds.

        Note:
            Does not commit. Caller must handle db.commit().
        """
        if total_bytes is not None:
            job.total_bytes = total_bytes
        if progress is not None:
            job.progress = progress
        if elapsed_seconds is not None:
            job.total_time_elapsed = elapsed_seconds
        if eta_seconds is not None:
            job.time_left = eta_seconds
        job.updated_at = datetime.utcnow()
        self.db.flush()

    def mark_completed(self, job: DownloadJobModel) -> None:
        """Mark download job as completed (100% progress).

        Args:
            job: Download job entity to mark as completed.

        Note:
            Does not commit. Caller must handle db.commit().
        """
        logger.info(f"Marking job {job.id} as completed")
        job.status = "completed"
        job.progress = 100.0
        job.updated_at = datetime.utcnow()
        self.db.flush()

    def mark_failed(self, job: DownloadJobModel, error_message: str) -> None:
        """Mark download job as failed and set error message.

        Args:
            job: Download job entity to mark as failed.
            error_message: Error message describing the failure.

        Note:
            Does not commit. Caller must handle db.commit().
        """
        logger.error(f"Marking job {job.id} as failed: {error_message}")
        job.status = "failed"
        job.error_message = error_message
        job.updated_at = datetime.utcnow()
        self.db.flush()

    def cleanup_job_files(self, job: DownloadJobModel) -> None:
        """Clean up temporary and final model files for failed/cancelled job.

        Args:
            job: Download job with file paths to clean up.

        Note:
            Removes files from disk but does not modify database records.
        """
        logger.info(f"Cleaning up files for job {job.id}")
        
        # Clean temp directory
        if job.temp_local_model_link and job.temp_local_model_link != "":
            if os.path.exists(job.temp_local_model_link):
                shutil.rmtree(job.temp_local_model_link, ignore_errors=True)
                logger.debug(f"Removed temp directory: {job.temp_local_model_link}")
            
            # Also check for temp_{id} pattern if not already in path
            if "temp" not in job.temp_local_model_link and job.local_model_id:
                temp_fallback = config.LLM_DIR / f"temp_{job.local_model_id}"
                if temp_fallback.exists():
                    shutil.rmtree(temp_fallback, ignore_errors=True)
                    logger.debug(f"Removed temp fallback: {temp_fallback}")
        
        # Clean final directory
        if job.final_local_model_link and job.final_local_model_link != "":
            if os.path.exists(job.final_local_model_link):
                shutil.rmtree(job.final_local_model_link, ignore_errors=True)
                logger.debug(f"Removed final directory: {job.final_local_model_link}")


def detect_supports_tools(local_path: Optional[str]) -> Optional[bool]:
    """Static tool-calling capability for a freshly downloaded model (#84).

    Reads the model's chat template via the active engine. Returns None (the
    column stays unset) when the engine or path is unavailable, or on any
    failure, so a detection problem never blocks download finalization and the
    model simply routes through the systematic KB path until recomputed.
    """
    engine = config.LLM_Engine
    if engine is None or not local_path:
        return None
    try:
        return engine.compute_supports_tools(local_path)
    except Exception:
        logger.warning(f"tool-calling detection failed for {local_path}")
        return None


def detect_supports_vision(local_path: Optional[str]) -> Optional[bool]:
    """Static vision (image-input) capability via the active engine (#133).

    Deterministic, no model load (mmproj presence for llama.cpp, ``config.json``
    for MLX). Returns None when the engine/path is unavailable or detection
    fails; the runtime treats None as not vision-capable (#212): images are
    stripped and the user is notified unless the capability is an explicit True.
    """
    engine = config.LLM_Engine
    if engine is None or not local_path:
        return None
    try:
        return engine.model_supports_vision(local_path)
    except Exception:
        logger.warning(f"vision detection failed for {local_path}")
        return None


def update_db_with_progress(job_tracker, job_id: int, model_id: int) -> None:
    """Background thread function that polls DownloadTracker and persists progress to database.

    Runs in daemon thread (started by download_llm service). Loops at 1Hz polling job.percent,
    updates DownloadJobModel row with progress/ETA/elapsed time. On completion, sets
    status="completed" and llm.local=1. On exception, marks status="failed" and cleans
    up temp files and LLM entry.

    This function is repository-level because its only job is database interaction. It runs
    in a separate thread with its own SessionLocal() instance to avoid SQLAlchemy threading
    conflicts with the main request thread.

    Args:
        job_tracker: DownloadTracker instance to poll for progress state (from services.py).
        job_id: Database primary key of DownloadJobModel to update.
        model_id: LLM ID to mark local=1 on successful completion.

    Warning:
        Runs in separate thread - uses separate SessionLocal() instance to avoid
        SQLAlchemy threading conflicts. This is the ONLY place in the codebase where
        we create a session outside the FastAPI request lifecycle.

    Example:
        >>> import threading
        >>> from src.domains.llms.services import DownloadTracker
        >>> tracker = DownloadTracker()
        >>> threading.Thread(
        ...     target=update_db_with_progress,
        ...     args=(tracker, 42, 15),
        ...     daemon=True
        ... ).start()
    """
    session = SessionLocal()
    try:
        dbj = session.query(DownloadJobModel).get(job_id)
        llm = session.query(Llm).get(model_id)
        if not dbj or not llm:
            logger.error(f"DB row for job {job_id} or model {model_id} not found")
            return

        start_time = datetime.utcnow()
        # Loop until download completes or is cancelled
        while job_tracker.percent < 100.0:
            time.sleep(1)
            # Exit cleanly if the job was cancelled (cancel endpoint handles DB cleanup)
            if not job_tracker.should_continue():
                logger.info(f"Job {job_id} cancelled, stopping progress tracking")
                return
            dbj.total_bytes = job_tracker.total_bytes
            dbj.progress = job_tracker.percent
            dbj.total_time_elapsed = (datetime.utcnow() - start_time).total_seconds()
            dbj.time_left = job_tracker.eta_seconds or 0.0
            session.commit()
            logger.debug(f"Job {job_id}: {dbj.progress:.2f}% complete")

        # Finalization (status=completed, local=1, supports_tools) is handled by
        # _run_download_task in its own session after download_llm returns. That
        # guarantees completion is recorded even if this thread's session hangs.
        logger.info(f"Job {job_id} progress tracking finished")
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed during progress tracking")
        try:
            dbj.status = "failed"
            dbj.error_message = str(e)
            
            # Clean up temp files
            if dbj.temp_local_model_link:
                if os.path.exists(dbj.temp_local_model_link):
                    shutil.rmtree(dbj.temp_local_model_link, ignore_errors=True)
                if "temp" not in dbj.temp_local_model_link:
                    temp_fallback = config.LLM_DIR / f"temp_{model_id}"
                    if temp_fallback.exists():
                        shutil.rmtree(temp_fallback, ignore_errors=True)
            
            if dbj.final_local_model_link and os.path.exists(dbj.final_local_model_link):
                shutil.rmtree(dbj.final_local_model_link, ignore_errors=True)
            
            # Delete the temp LLM entry
            session.delete(llm)
            session.commit()
            
        except Exception as cleanup_error:
            logger.exception(f"Failed to cleanup after job {job_id} failure: {cleanup_error}")
            
    finally:
        session.close()
