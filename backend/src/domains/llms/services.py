"""Business logic for LLM download orchestration with progress tracking and quantization.

This module manages the complete lifecycle of downloading LLM models from HuggingFace,
tracking progress in real-time, and converting to engine-specific formats (e.g., MLX 4-bit).

Architecture:
    1. download_llm() orchestrates the full pipeline (download → quantize → cleanup).
    2. DownloadTracker monitors progress and ETA across concurrent file downloads.
    3. make_callback() creates fsspec hooks to update DownloadTracker on each chunk.
    4. update_db_with_progress() runs in background thread to persist status to DB.
    5. download_files_concurrent() parallelizes .safetensors shard downloads.

Engine Integration:
    - Checks llm.quantized flag to determine if model is pre-quantized (MLX format).
    - Pre-quantized models skip local quantization and are moved directly to final dir.
    - Non-quantized models are converted via config.LLM_Engine.quant_and_save_from_hf_format().

Download Flow:
    ┌─────────────┐
    │ HuggingFace │
    │  Repository │
    └──────┬──────┘
           │ (1) List files & compute total bytes
           ↓
    ┌──────────────┐
    │ temp_save_dir│ ← Download .safetensors + config files
    └──────┬───────┘
           │ (2) Check llm.quantized flag
           ↓
    ┌─────────────┐
    │  Quantize?  │ → YES → config.LLM_Engine.quant_and_save_from_hf_format()
    └─────────────┘ → NO  → shutil.move to final_save_dir
           ↓
    ┌──────────────┐
    │final_save_dir│ ← Ready for inference
    └──────────────┘

Example:
    from src.domains.llms.services import download_llm
    import asyncio

    # Download and quantize Llama-3-8B
    final_path = asyncio.run(download_llm(
        model_link="meta-llama/Llama-3-8B-Instruct",
        model_id=42,
        temp_save_dir=config.LLM_DIR / "temp_42",
        final_save_dir=config.LLM_DIR / "42",
        job_id=15
    ))
    # → Downloads to temp, quantizes to MLX 4-bit, saves to final, updates job #15
"""

import os
import time
import threading
import shutil
import asyncio
from threading import Lock
from typing import Optional, List, Tuple

from huggingface_hub import HfApi, HfFileSystem
from huggingface_hub.utils import GatedRepoError, HfHubHTTPError
from fsspec.callbacks import Callback

from src.database.core import SessionLocal
from src.domains.llms.repository import update_db_with_progress
from src.entities.Llm import Llm

from src.core.config import HF_TOKEN
from src.core import config
from src.core.logging import logger
from src.core.exceptions import (
    DownloadJobNotFoundException,
    ModelNotFoundException,
    InvalidInputException,
    StateConflictException,
    UnsupportedPlatformException,
)

# Environment setup
FILES_TO_EXCLUDE = ["consolidated.safetensors"]

# Registry of active download trackers keyed by job_id for cancellation support
_active_trackers: dict = {}
_trackers_lock = threading.Lock()


def _register_tracker(job_id: int, tracker: "DownloadTracker") -> None:
    with _trackers_lock:
        _active_trackers[job_id] = tracker


def _unregister_tracker(job_id: int) -> None:
    with _trackers_lock:
        _active_trackers.pop(job_id, None)


def get_active_download_tracker(job_id: int) -> Optional["DownloadTracker"]:
    with _trackers_lock:
        return _active_trackers.get(job_id)


GGUF_QUANT_PRIORITY = ["q4_k_m", "q4_0", "q5_k_m", "q8_0", "f16"]


def pick_best_gguf(filenames: list[str]) -> str | None:
    """From a list of filenames in a GGUF repo, return the best quantization.

    Uses the same priority order as CUDA_Engine._select_gguf so behavior is
    consistent between download-time selection and load-time selection.

    Args:
        filenames: All filenames returned by HfApi.list_repo_files().

    Returns:
        Filename of the chosen GGUF, or None if no .gguf files found.
    """
    # Exclude multimodal projection files (mmproj-*.gguf) — these are vision
    # encoder weights, not the main text model, and must not be loaded as LLM.
    ggufs = [
        f for f in filenames
        if f.lower().endswith(".gguf") and not f.lower().startswith("mmproj")
    ]
    if not ggufs:
        return None
    for quant in GGUF_QUANT_PRIORITY:
        for name in ggufs:
            if quant in name.lower():
                logger.info(f"Selected GGUF: {name} (quant={quant})")
                return name
    # Fall back to the first one alphabetically
    chosen = sorted(ggufs)[0]
    logger.warning(f"No preferred quant found; falling back to {chosen}")
    return chosen


def get_quantized_model_link(original_link: str) -> str:
    """Resolve engine-specific quantized model link from MODEL_MAPPING if available.

    Checks config.LLM_Engine.MODEL_MAPPING for a pre-quantized variant (e.g., MLX 4-bit
    version). If found, returns the quantized link; otherwise returns original unchanged.

    Args:
        original_link: HuggingFace model ID (e.g., "meta-llama/Llama-3-8B-Instruct").

    Returns:
        Quantized model link if mapping exists, otherwise original_link.

    Example:
        >>> link = get_quantized_model_link("meta-llama/Llama-3-8B-Instruct")
        >>> print(link)
        "mlx-community/Meta-Llama-3-8B-Instruct-4bit"  # or original if not mapped
    """
    quantized_link = config.LLM_Engine.MODEL_MAPPING.get(original_link, original_link)
    if quantized_link != original_link:
        logger.info(f"Using quantized model: {original_link} -> {quantized_link}")
    return quantized_link


class DownloadTracker:
    """Thread-safe progress tracker for multi-file downloads with ETA estimation.

    Aggregates downloaded bytes across concurrent file transfers and periodically
    computes ETA based on moving average of download rate. Used by fsspec callbacks
    and background DB updater thread.

    Attributes:
        total_bytes: Total download size in bytes (set before download starts).
        downloaded_bytes: Bytes downloaded so far (updated by callbacks).
        eta_seconds: Estimated seconds remaining (None until first ETA computation).

    Example:
        >>> tracker = DownloadTracker()
        >>> tracker.total_bytes = 1_000_000_000
        >>> tracker.update(50_000_000)
        >>> print(tracker.percent)
        5.0
    """

    def __init__(self) -> None:
        self.total_bytes: int = 0
        self.downloaded_bytes: int = 0
        self.eta_seconds: Optional[float] = None
        self._lock = Lock()
        self._cancelled: bool = False
        logger.info("DownloadJob initialized")

    def update(self, bytes_downloaded: int) -> None:
        """Atomically increment downloaded byte count (thread-safe).

        Args:
            bytes_downloaded: Number of bytes downloaded in this chunk transfer.
        """
        with self._lock:
            self.downloaded_bytes += bytes_downloaded

    @property
    def percent(self) -> float:
        """Compute download completion percentage with zero-division guard.

        Returns:
            Progress percentage in range [0.0, 100.0]. Returns 0.0 if total_bytes is 0.
        """
        if self.total_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100

    def cancel(self) -> None:
        """Signal download cancellation (thread-safe)."""
        with self._lock:
            self._cancelled = True

    def should_continue(self) -> bool:
        """Return False if cancelled, True otherwise (thread-safe)."""
        with self._lock:
            return not self._cancelled

    async def monitor_eta(self, interval: float = 20.0) -> None:
        """Continuously estimate remaining time based on download rate (runs until 100%).

        Samples downloaded_bytes at regular intervals, computes delta rate, and updates
        eta_seconds. Runs as asyncio task in background until download completes.

        Args:
            interval: Seconds between ETA recalculations (default 20s).

        Example:
            >>> tracker = DownloadTracker()
            >>> eta_task = asyncio.create_task(tracker.monitor_eta(interval=5.0))
            >>> # ... download happens in parallel ...
            >>> await eta_task  # Wait for completion
        """
        logger.info("Starting ETA monitoring")
        last_time = time.time()
        last_downloaded = 0
        while True:
            await asyncio.sleep(interval)
            with self._lock:
                current = self.downloaded_bytes
                total = self.total_bytes
            if current >= total:
                break

            now = time.time()
            delta_bytes = current - last_downloaded
            delta_time = now - last_time

            if delta_time > 0 and delta_bytes > 0:
                rate = delta_bytes / delta_time
                self.eta_seconds = (total - current) / rate

            last_time = now
            last_downloaded = current

        logger.info("ETA monitoring complete")


def make_callback(job: DownloadTracker) -> Callback:
    """Create fsspec Callback that updates DownloadTracker on each file transfer chunk.

    The callback's transfer-chunk hook is invoked by fsspec after each network read.
    Computes delta bytes since last update to avoid double-counting (guards against
    negative deltas from fsspec resets).

    Args:
        job: DownloadTracker instance to update with progress.

    Returns:
        Configured fsspec Callback with total size and chunk hook.

    Example:
        >>> tracker = DownloadTracker()
        >>> tracker.total_bytes = 1_000_000
        >>> callback = make_callback(tracker)
        >>> fs.get_file("repo/file.safetensors", "local.safetensors", callback)
    """
    def after_chunk(size: int, value: int, **kwargs) -> None:
        """Update download progress after receiving a chunk from HuggingFace.
        
        Nested callback invoked by huggingface_hub after each file chunk transfer.
        Calculates delta bytes and updates the DownloadTracker with progress.
        
        Args:
            size: Total file size in bytes.
            value: Cumulative bytes downloaded so far.
            **kwargs: Additional metadata from huggingface_hub (ignored).
        
        Returns:
            None
        """
        # Calculate bytes since last update and guard against negative
        delta = value - job.downloaded_bytes if value is not None else 0
        job.update(max(delta, 0))

    return Callback(size=job.total_bytes, hooks={"transfer-chunk": after_chunk})


async def download_files_concurrent(
    fs: HfFileSystem,
    callback: Callback,
    tasks: List[Tuple[str, str]],
    local_dir: str
) -> None:
    """Download multiple HuggingFace files in parallel using asyncio executor pool.

    Wraps synchronous fs.get_file() calls in run_in_executor to achieve I/O concurrency.
    Useful for downloading .safetensors shards simultaneously to maximize bandwidth.

    Args:
        fs: HfFileSystem instance with auth token.
        callback: fsspec Callback for progress tracking (shared across all files).
        tasks: List of (repo_id, file_path) tuples to download.
        local_dir: Base directory to save files (subdirectories created as needed).

    Example:
        >>> fs = HfFileSystem(token=HF_TOKEN)
        >>> callback = make_callback(tracker)
        >>> tasks = [("meta-llama/Llama-3-8B", "model-00001-of-00004.safetensors"), ...]
        >>> await download_files_concurrent(fs, callback, tasks, config.LLM_DIR / "temp_42")
    """
    loop = asyncio.get_running_loop()
    coros = []
    for repo_id, path in tasks:
        remote = f"{repo_id}/{path}"
        dest = os.path.join(local_dir, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        coros.append(loop.run_in_executor(None, fs.get_file, remote, dest, callback))
    await asyncio.gather(*coros)


def _assert_runnable(model_link: str, actual_download_link: str) -> None:
    """Reject a download whose resolved target won't run on the active engine.

    Routing always points at a public quant; if the resolved link is still a gated
    first-party id (mapping miss) or a KNOWN_BROKEN quant, fail up front with a clear
    message rather than letting a 401 surface as a 500 mid-transfer.
    """
    if not config.LLM_Engine.is_runnable(actual_download_link):
        raise UnsupportedPlatformException(
            feature=model_link,
            reason=f"no runnable model format is published for {config.LLM_Engine.__name__}",
        )


async def download_llm(
    model_link: str,
    model_id: int,
    temp_save_dir: str,
    final_save_dir: str,
    job_id: Optional[int] = None
) -> str:
    """Download HuggingFace model with progress tracking and engine-specific quantization.

    Complete pipeline: list repo files → download to temp_save_dir → quantize (if needed)
    → save to final_save_dir. Pre-quantized models (llm.quantized=1) skip local conversion
    and are moved directly. Progress updates are persisted to DownloadJobModel if job_id provided.

    Args:
        model_link: HuggingFace repo ID (e.g., "meta-llama/Llama-3-8B-Instruct").
        model_id: Database ID of the LLM entry (used to check quantized flag).
        temp_save_dir: Temp directory for full-precision download (deleted after quantization).
        final_save_dir: Final directory for quantized model (ready for inference).
        job_id: Optional DownloadJobModel ID for progress tracking (spawns background thread).

    Returns:
        Path to temp_save_dir (note: may be deleted if quantization successful).

    Raises:
        Exception: If HuggingFace API fails, download fails, or quantization fails.

    Example:
        >>> final_path = await download_llm(
        ...     model_link="meta-llama/Llama-3-8B-Instruct",
        ...     model_id=42,
        ...     temp_save_dir=config.LLM_DIR / "temp_42",
        ...     final_save_dir=config.LLM_DIR / "42",
        ...     job_id=15
        ... )
        >>> # Progress tracked in DownloadJobModel(id=15), final model in backend/data/models/42
    """
    # Check if model is already quantized from database
    session = SessionLocal()
    llm = session.query(Llm).get(model_id)
    is_prequantized = llm.quantized if llm else False
    session.close()

    # Check if this engine uses GGUF repos (CUDA only) and has a mapping for this model.
    # If so, download the single best GGUF directly and skip local conversion entirely.
    # For MLX, MODEL_MAPPING points to mlx-community repos (not GGUF) — handled separately.
    _uses_gguf = getattr(config.LLM_Engine, 'USES_GGUF', False)
    _mapped_repo = config.LLM_Engine.MODEL_MAPPING.get(model_link)
    gguf_repo = _mapped_repo if (_uses_gguf and _mapped_repo) else None

    if _mapped_repo:
        logger.info(f"Mapped repo found: {model_link} -> {_mapped_repo}")
        actual_download_link = _mapped_repo
        is_prequantized = True
    else:
        actual_download_link = model_link

    # Runnability gate: only ever fetch a public quant THIS engine can run.
    _assert_runnable(model_link, actual_download_link)

    # Prepare local path
    os.makedirs(temp_save_dir, exist_ok=True)
    os.makedirs(final_save_dir, exist_ok=True)
    logger.info(f"Starting download for {model_link} → {temp_save_dir}")
    if is_prequantized:
        logger.info(f"Model is pre-quantized (MLX), downloading directly: {actual_download_link}")
    else:
        logger.info("Model will be quantized locally after download")

    # Initialize HF API & filesystem
    api = HfApi(token=HF_TOKEN)
    fs = HfFileSystem(token=HF_TOKEN)

    # Initialize tracking and register for cancellation support
    job = DownloadTracker()
    if job_id is not None:
        _register_tracker(job_id, job)

    try:
        # Gather file sizes and compute total
        info = api.repo_info(actual_download_link, files_metadata=True)
        file_sizes = {
            s.rfilename: s.size
            for s in info.siblings
            if s.size and s.rfilename not in FILES_TO_EXCLUDE
        }
        job.total_bytes = sum(file_sizes.values())
        logger.info(f"Total size: {job.total_bytes} bytes")

        # Create progress callback
        callback = make_callback(job)
        callback.set_size(job.total_bytes)

        # Start DB updater if requested
        if job_id is not None:
            threading.Thread(
                target=update_db_with_progress,
                args=(job, job_id, model_id),
                daemon=True
            ).start()

        # Start ETA monitoring
        eta_task = asyncio.create_task(job.monitor_eta(interval=5.0))

        # Build the file list to download.
        # For GGUF repos: pick only the single best quantization + small aux files.
        # For safetensors repos: download everything (then convert locally).
        all_repo_files = list(api.list_repo_files(actual_download_link))
        if gguf_repo:
            best_gguf = pick_best_gguf(all_repo_files)
            if not best_gguf:
                raise Exception(f"No .gguf files found in repo {actual_download_link}")
            small_aux = [
                f for f in all_repo_files
                if not f.lower().endswith(".gguf")
                and f in file_sizes
                and file_sizes.get(f, 0) < 10 * 1024 * 1024  # < 10 MB
            ]
            all_files = [best_gguf] + small_aux
            job.total_bytes = sum(file_sizes.get(f, 0) for f in all_files)
            callback.set_size(job.total_bytes)
            logger.info(f"GGUF download: {best_gguf} + {len(small_aux)} aux files")
        else:
            all_files = [f for f in all_repo_files if f in file_sizes]

        misc = [f for f in all_files if not f.endswith(".safetensors")]
        shards = [f for f in all_files if f.endswith(".safetensors")]

        # Download misc sequentially
        for path in misc:
            await asyncio.to_thread(fs.get_file, f"{actual_download_link}/{path}", os.path.join(temp_save_dir, path), callback)
            logger.info(f"Downloaded {path}")

        # Download shards concurrently
        shard_tasks = [(actual_download_link, path) for path in shards]
        await download_files_concurrent(fs, callback, shard_tasks, temp_save_dir)
        logger.info("All shards downloaded")

        # If cancelled while shards were in-flight, stop here — cancel endpoint already cleaned up
        if not job.should_continue():
            logger.info(f"Download job {job_id} was cancelled during transfer, skipping finalization")
            return temp_save_dir

        # If pre-quantized, just move files; otherwise convert locally
        if is_prequantized:
            logger.info("Using pre-quantized model, moving files directly")
            if not os.path.exists(temp_save_dir):
                logger.warning(f"temp dir {temp_save_dir} missing (cancelled?), skipping move")
                return temp_save_dir
            if os.path.exists(final_save_dir):
                shutil.rmtree(final_save_dir, ignore_errors=True)
            shutil.move(temp_save_dir, final_save_dir)
        else:
            await asyncio.to_thread(config.LLM_Engine.quant_and_save_from_hf_format, temp_save_dir, final_save_dir)
            shutil.rmtree(temp_save_dir, ignore_errors=True)

        # Wait for ETA monitor to finish
        await eta_task
        logger.info("Download complete")

        return temp_save_dir

    except (GatedRepoError, HfHubHTTPError) as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if isinstance(e, GatedRepoError) or status in (401, 403):
            logger.error(f"Anonymous access denied for {actual_download_link}: {e}")
            raise UnsupportedPlatformException(
                feature=model_link,
                reason="requires HuggingFace authentication and cannot be downloaded anonymously",
            )
        logger.error(f"HuggingFace error for {actual_download_link}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to process model: {e}")
        raise
    finally:
        if job_id is not None:
            _unregister_tracker(job_id)


def cancel_download_job(job_id: int, job_repo, llm_repo, db) -> dict:
    """Cancel an active download job, signal the tracker, and clean up partial files.

    Args:
        job_id: ID of the download job to cancel.
        job_repo: Download_Job_Repository instance.
        llm_repo: Llm_Repository instance.
        db: SQLAlchemy session for transaction control.

    Returns:
        dict with cancellation status.

    Raises:
        DownloadJobNotFoundException, ModelNotFoundException,
        InvalidInputException, StateConflictException
    """
    job = job_repo.get_by_id(job_id)
    if not job:
        raise DownloadJobNotFoundException(job_id)
    if job.status in ["completed", "failed", "cancelled"]:
        raise StateConflictException(
            "Cannot cancel a job that is already completed, failed, or cancelled"
        )

    llm = llm_repo.get_by_id(job.local_model_id)
    if not llm:
        raise ModelNotFoundException(f"LLM {job.local_model_id}")
    if llm.local != 2:
        raise InvalidInputException(
            "Download ended - cannot be cancelled, please delete the model"
        )

    # Signal running download thread to stop
    tracker = get_active_download_tracker(job_id)
    if tracker:
        tracker.cancel()
        logger.info(f"Signaled cancellation for download job {job_id}")
    else:
        logger.warning(f"No active tracker for job {job_id}, proceeding with cleanup")

    # Clean up files and remove the pending LLM entry
    job_repo.update_status(job, "cancelled")
    job_repo.cleanup_job_files(job)
    llm_repo.delete(llm)
    db.commit()

    logger.info(f"Cancelled download job {job_id} and deleted temp LLM {llm.id}")
    return {"message": "Download cancellation initiated", "job_id": job_id, "status": "cancelled"}