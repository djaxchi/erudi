"""Business logic for LLM download orchestration with progress tracking.

This module manages the complete lifecycle of downloading LLM models from HuggingFace
and tracking progress in real-time. Every catalog link is a pre-built engine-format
quant, so downloads are moved into place with no local conversion.

Architecture:
    1. download_llm() orchestrates the full pipeline (select files → download → move).
    2. _select_download_files() picks the exact files to fetch (single best GGUF quant).
    3. DownloadTracker monitors progress and ETA across concurrent file downloads.
    4. make_callback() creates fsspec hooks to update DownloadTracker on each chunk.
    5. update_db_with_progress() runs in background thread to persist status to DB.
    6. download_files_concurrent() parallelizes .safetensors shard downloads.

Engine Integration:
    - Every catalog link is a pre-built engine-format quant; no local conversion.
    - GGUF engines (USES_GGUF) download one best quant file + mmproj + small aux files.

Download Flow:
    ┌─────────────┐
    │ HuggingFace │
    │  Repository │
    └──────┬──────┘
           │ (1) Select files & compute total bytes
           ↓
    ┌──────────────┐
    │ temp_save_dir│ ← Download model weights + config files
    └──────┬───────┘
           │ (2) shutil.move
           ↓
    ┌──────────────┐
    │final_save_dir│ ← Ready for inference
    └──────────────┘

Example:
    from src.domains.llms.services import download_llm
    import asyncio

    # Download a pre-built quant of Llama-3-8B
    final_path = asyncio.run(download_llm(
        model_link="meta-llama/Llama-3-8B-Instruct",
        model_id=42,
        temp_save_dir=config.LLM_DIR / "temp_42",
        final_save_dir=config.LLM_DIR / "42",
        job_id=15
    ))
    # → Downloads to temp, moves to final, updates job #15
"""

import os
import time
import threading
import shutil
import asyncio
from threading import Lock
from typing import NamedTuple, Optional, List, Tuple

from huggingface_hub import HfApi, HfFileSystem
from huggingface_hub.utils import GatedRepoError, HfHubHTTPError
from fsspec.callbacks import Callback

from src.domains.llms.repository import update_db_with_progress

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


class _DownloadSelection(NamedTuple):
    """Files chosen for download, with the GGUF picks kept for logging."""

    files: List[str]
    best_gguf: Optional[str]
    mmproj_files: List[str]
    small_aux: List[str]


def _select_download_files(
    all_repo_files: List[str],
    file_sizes: dict,
    uses_gguf: bool,
) -> _DownloadSelection:
    """Pick the exact files to download from a repo listing (pure, no I/O).

    GGUF repos: the single best quantization (pick_best_gguf) + mmproj gguf
    files + auxiliary non-gguf files with a known size under 10 MB. When the
    repo has no .gguf at all, best_gguf is None and files is empty — the
    caller raises with the repo id in the message.

    Non-GGUF repos: every repo file with a known size (exclusions were already
    applied when building file_sizes).

    Args:
        all_repo_files: All filenames returned by HfApi.list_repo_files().
        file_sizes: Filename → size in bytes, exclusions already removed.
        uses_gguf: Whether the active engine consumes GGUF repos.

    Returns:
        _DownloadSelection with the files to download and the GGUF picks.
    """
    if not uses_gguf:
        return _DownloadSelection(
            files=[f for f in all_repo_files if f in file_sizes],
            best_gguf=None,
            mmproj_files=[],
            small_aux=[],
        )
    best_gguf = pick_best_gguf(all_repo_files)
    if not best_gguf:
        return _DownloadSelection(files=[], best_gguf=None, mmproj_files=[], small_aux=[])
    mmproj_files = [
        f for f in all_repo_files
        if "mmproj" in f.lower() and f.lower().endswith(".gguf")
    ]
    small_aux = [
        f for f in all_repo_files
        if not f.lower().endswith(".gguf")
        and f in file_sizes
        and file_sizes.get(f, 0) < 10 * 1024 * 1024  # < 10 MB
    ]
    return _DownloadSelection(
        files=[best_gguf] + mmproj_files + small_aux,
        best_gguf=best_gguf,
        mmproj_files=mmproj_files,
        small_aux=small_aux,
    )


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


def _assert_runnable(model_link: str) -> None:
    """Reject a download for a KNOWN_BROKEN quant up front.

    Every catalog link is already a public engine-format quant (built from a
    filter=FORMAT_TAG search), so the only thing to reject is a quant flagged as
    crash-on-load for this engine — fail fast with a clear message.
    """
    if not config.LLM_Engine.is_runnable(model_link):
        raise UnsupportedPlatformException(
            feature=model_link,
            reason=f"this model is known not to run on {config.LLM_Engine.__name__}",
        )


async def download_llm(
    model_link: str,
    model_id: int,
    temp_save_dir: str,
    final_save_dir: str,
    job_id: Optional[int] = None
) -> str:
    """Download a pre-built HuggingFace quant with progress tracking.

    Complete pipeline: list repo files → select files to download → download to
    temp_save_dir → move to final_save_dir. Every catalog link is a pre-built quant,
    so no local conversion happens. Progress updates are persisted to
    DownloadJobModel if job_id provided.

    Args:
        model_link: HuggingFace repo ID (e.g., "meta-llama/Llama-3-8B-Instruct").
        model_id: Database ID of the LLM entry (used by the DB progress updater).
        temp_save_dir: Temp directory for the download (moved to final_save_dir on success).
        final_save_dir: Final directory for the model (ready for inference).
        job_id: Optional DownloadJobModel ID for progress tracking (spawns background thread).

    Returns:
        Path to temp_save_dir (note: moved to final_save_dir on success).

    Raises:
        Exception: If HuggingFace API fails, the download fails, or a GGUF repo has no .gguf.

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
    # The catalog link IS already a public engine-format quant (resolved at seed
    # time from a filter=FORMAT_TAG search), so we download it directly — no mapping.
    actual_download_link = model_link
    _assert_runnable(model_link)

    # Everything we download is a pre-built quant → no local conversion. GGUF repos
    # additionally need only the single best quant file picked (pick_best_gguf).
    _uses_gguf = getattr(config.LLM_Engine, 'USES_GGUF', False)

    # Prepare local path
    os.makedirs(temp_save_dir, exist_ok=True)
    os.makedirs(final_save_dir, exist_ok=True)
    logger.info(f"Starting download for {model_link} → {temp_save_dir}")
    logger.info(f"Downloading pre-built quant directly: {actual_download_link}")

    # Initialize HF API & filesystem
    api = HfApi(token=HF_TOKEN)
    fs = HfFileSystem(token=HF_TOKEN)

    # Initialize tracking and register for cancellation support
    job = DownloadTracker()
    if job_id is not None:
        _register_tracker(job_id, job)

    try:
        # Gather file sizes, then select the exact files to download BEFORE
        # computing the total, so the logged size and progress reflect what is
        # actually fetched (a single GGUF quant, not the whole repo).
        info = api.repo_info(actual_download_link, files_metadata=True)
        file_sizes = {
            s.rfilename: s.size
            for s in info.siblings
            if s.size and s.rfilename not in FILES_TO_EXCLUDE
        }
        all_repo_files = list(api.list_repo_files(actual_download_link))
        selection = _select_download_files(all_repo_files, file_sizes, _uses_gguf)
        if _uses_gguf and selection.best_gguf is None:
            raise Exception(f"No .gguf files found in repo {actual_download_link}")
        all_files = selection.files
        if _uses_gguf:
            if selection.mmproj_files:
                logger.info(
                    f"GGUF download: {selection.best_gguf} + mmproj ({selection.mmproj_files[0]}) "
                    f"+ {len(selection.small_aux)} aux files"
                )
            else:
                logger.info(
                    f"GGUF download: {selection.best_gguf} + {len(selection.small_aux)} aux files"
                )

        job.total_bytes = sum(file_sizes.get(f, 0) for f in all_files)
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

        # Everything is a pre-built quant: move files straight to the final dir
        logger.info("Moving downloaded files to final location")
        if not os.path.exists(temp_save_dir):
            logger.warning(f"temp dir {temp_save_dir} missing (cancelled?), skipping move")
            return temp_save_dir
        if os.path.exists(final_save_dir):
            shutil.rmtree(final_save_dir, ignore_errors=True)
        shutil.move(temp_save_dir, final_save_dir)

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