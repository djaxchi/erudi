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
        temp_save_dir="/data/models/temp_42",
        final_save_dir="/data/models/42",
        job_id=15
    ))
    # → Downloads to temp, quantizes to MLX 4-bit, saves to final, updates job #15
"""

import os, time, threading, shutil, asyncio
from datetime import datetime
from threading import Lock
from typing import Optional, List, Tuple

from huggingface_hub import HfApi, HfFileSystem
from fsspec.callbacks import Callback

from src.database.core import SessionLocal
from src.entities.DownloadJob import DownloadJobModel
from src.entities.Llm import Llm

from src.core.config import HF_TOKEN
from src.core import config
from src.core.logging import logger

# Environment setup
FILES_TO_EXCLUDE = ["consolidated.safetensors"]


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
        # Calculate bytes since last update and guard against negative
        delta = value - job.downloaded_bytes if value is not None else 0
        job.update(max(delta, 0))

    return Callback(size=job.total_bytes, hooks={"transfer-chunk": after_chunk})


def update_db_with_progress(job: DownloadTracker, job_id: int, model_id: int) -> None:
    """Background thread that polls DownloadTracker and persists progress to database.

    Runs in daemon thread (started by download_llm). Loops at 1Hz polling job.percent,
    updates DownloadJobModel row with progress/ETA/elapsed time. On completion, sets
    status="completed" and llm.local=1. On exception, marks status="failed" and cleans
    up temp files and LLM entry.

    Args:
        job: DownloadTracker instance to poll for progress state.
        job_id: Database primary key of DownloadJobModel to update.
        model_id: LLM ID to mark local=1 on successful completion.

    Warning:
        Runs in separate thread - uses separate SessionLocal() instance to avoid
        SQLAlchemy threading conflicts.

    Example:
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
        # Loop until download completes
        while job.percent < 100.0:
            time.sleep(1)
            dbj.total_bytes = job.total_bytes
            dbj.progress = job.percent
            dbj.total_time_elapsed = (datetime.utcnow() - start_time).total_seconds()
            dbj.time_left = job.eta_seconds or 0.0
            session.commit()
            logger.info(f"Job {job_id}: {dbj.progress:.2f}% complete")

        # Finalize job state
        dbj.progress = 100.0
        dbj.status = "completed"
        llm.local = 1
        session.commit()
    except Exception as e:
        dbj.status = "failed"
        dbj.error_message = str(e)
        job.local_model_id = -1
        shutil.rmtree(job.local_model_link, ignore_errors=True)
        job.local_model_link = ""
        job.updated_at = datetime.now()
        session.delete(llm)
        session.commit()
        logger.error(f"Job {job_id} failed: {e}")
    finally:
        session.close()


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
        >>> await download_files_concurrent(fs, callback, tasks, "/data/models/temp_42")
    """
    loop = asyncio.get_running_loop()
    coros = []
    for repo_id, path in tasks:
        remote = f"{repo_id}/{path}"
        dest = os.path.join(local_dir, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        coros.append(loop.run_in_executor(None, fs.get_file, remote, dest, callback))
    await asyncio.gather(*coros)


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
        ...     temp_save_dir="/data/models/temp_42",
        ...     final_save_dir="/data/models/42",
        ...     job_id=15
        ... )
        >>> # Progress tracked in DownloadJobModel(id=15), final model in /data/models/42
    """
    # Check if model is already quantized from database
    session = SessionLocal()
    llm = session.query(Llm).get(model_id)
    is_prequantized = llm.quantized == 1 if llm else False
    session.close()
    
    # The link stored in DB is already the MLX link for pre-quantized models
    actual_download_link = model_link
    
    # Prepare local path
    os.makedirs(temp_save_dir, exist_ok=True)
    os.makedirs(final_save_dir, exist_ok=True)
    logger.info(f"Starting download for {model_link} → {temp_save_dir}")
    if is_prequantized:
        logger.info(f"Model is pre-quantized (MLX), downloading directly: {actual_download_link}")
    else:
        logger.info(f"Model will be quantized locally after download")

    # Initialize HF API & filesystem
    api = HfApi(token=HF_TOKEN)
    fs = HfFileSystem(token=HF_TOKEN)

    # Initialize tracking
    job = DownloadTracker()

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

    # Split tasks into misc and shard files
    all_files = [f for f in api.list_repo_files(actual_download_link) if f in file_sizes]
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

    # If pre-quantized, just move files; otherwise convert locally
    try:
        if is_prequantized:
            # Already quantized in the right format, just move to final directory
            logger.info("Using pre-quantized model, moving files directly")
            if os.path.exists(final_save_dir):
                shutil.rmtree(final_save_dir, ignore_errors=True)
            shutil.move(temp_save_dir, final_save_dir)
        else:
            # Need to convert to right format and quantize locally
            await asyncio.to_thread(config.LLM_Engine.quant_and_save_from_hf_format, temp_save_dir, final_save_dir)
            shutil.rmtree(temp_save_dir, ignore_errors=True)
    except Exception as e:
        logger.error(f"Failed to process model: {e}")
        raise
    
    # Wait for ETA monitor to finish
    await eta_task
    logger.info("Download complete")

    return temp_save_dir