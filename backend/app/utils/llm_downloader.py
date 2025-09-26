"""
Utility for downloading LLM repositories from Hugging Face with progress
tracking and database updates.
"""

# Standard library imports
import os
import time
import threading
import shutil
import logging
import asyncio
import mlx_lm
from datetime import datetime
from threading import Lock
from typing import Callable, Optional, List, Tuple

# Third-party imports
import torch  # type: ignore
from huggingface_hub import HfApi, HfFileSystem  # type: ignore
from fsspec.callbacks import Callback  # type: ignore

# Local application imports
from ..database import SessionLocal
from ..models.DownloadJob import DownloadJobModel
from ..models.Llm import Llm

# Configure logger
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

# Environment setup
HF_TOKEN = os.getenv("HF_TOKEN", "")
FILES_TO_EXCLUDE = ["consolidated.safetensors"]


class DownloadTracker:
    """
    Tracks download progress across multiple files and estimates ETA.

    Attributes:
        total_bytes (int): Total bytes to download.
        downloaded_bytes (int): Bytes downloaded so far.
        eta_seconds (Optional[float]): Estimated seconds remaining.
    """

    def __init__(self) -> None:
        self.total_bytes: int = 0
        self.downloaded_bytes: int = 0
        self.eta_seconds: Optional[float] = None
        self._lock = Lock()
        logger.info("DownloadJob initialized")

    def update(self, bytes_downloaded: int) -> None:
        """
        Update the downloaded byte count for the job.

        Args:
            bytes_downloaded (int): Number of bytes downloaded in this chunk.
        """
        with self._lock:
            self.downloaded_bytes += bytes_downloaded

    @property
    def percent(self) -> float:
        """
        Compute the percentage of completion.

        Returns:
            float: Progress percentage [0.0–100.0].
        """
        if self.total_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100

    async def monitor_eta(self, interval: float = 20.0) -> None:
        """
        Periodically estimate remaining time based on current download rate.

        Args:
            interval (float): Seconds between ETA calculations.
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
    """
    Create an fsspec Callback to update DownloadJob on each transfer chunk.

    Args:
        job (DownloadJob): Tracker instance to update.

    Returns:
        Callback: Configured fsspec callback.
    """
    def after_chunk(size: int, value: int, **kwargs) -> None:
        # Calculate bytes since last update and guard against negative
        delta = value - job.downloaded_bytes if value is not None else 0
        job.update(max(delta, 0))

    return Callback(size=job.total_bytes, hooks={"transfer-chunk": after_chunk})


def update_db_with_progress(job: DownloadTracker, job_id: int, model_id: int) -> None:
    """
    Periodically update DownloadJobModel row in the database.

    Args:
        job (DownloadJob): Tracker instance with progress state.
        job_id (int): Primary key of the DownloadJobModel to update.
        model_id (int): LLM model ID to mark local on completion.
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
    """
    Download multiple files concurrently using asyncio Executor.

    Args:
        fs (HfFileSystem): Hugging Face filesystem instance.
        callback (Callback): Callback for progress updates.
        tasks (List[Tuple[str,str]]): List of (repo_id, file_path).
        local_dir (str): Base local directory to save files.
    """
    loop = asyncio.get_running_loop()
    coros = []
    for repo_id, path in tasks:
        remote = f"{repo_id}/{path}"
        dest = os.path.join(local_dir, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        coros.append(loop.run_in_executor(None, fs.get_file, remote, dest, callback))
    await asyncio.gather(*coros)

async def convert_hf_mlx(hf_dir: str, mlx_dir: str):
    """Convert Hugging Face model to MLX format."""
    try:
        logger.info(f"Starting conversion from HF to MLX")
        start = datetime.now()
        if os.path.exists(mlx_dir):
            shutil.rmtree(mlx_dir, ignore_errors=True)
        mlx_lm.convert(
            hf_dir,
            mlx_path=mlx_dir,
            quantize=True,
            q_bits=4
        )
        logger.info(f"Model converted to mlx in {datetime.now() - start}")
    except:
        raise


async def download_llm(
    model_link: str,
    model_id: int,
    temp_save_dir: str,
    final_save_dir: str,
    job_id: Optional[int] = None
) -> str:
    """
    Download a Hugging Face repo with progress tracking and optional DB updates.

    Args:
        model_link (str): Hugging Face repo ID.
        model_id (int): Database ID of the LLM model.
        temp_save_dir (str): Temporary directory for full-precision model.
        final_save_dir (str): Final directory for mlx quantized model.
        job_id (Optional[int]): DownloadJobModel ID to update.

    Returns:
        str: Final local path containing downloaded files.
    """
    # Prepare local path
    os.makedirs(temp_save_dir, exist_ok=True)
    logger.info(f"Starting download for {model_link} → {temp_save_dir}")

    # Initialize HF API & filesystem
    api = HfApi(token=HF_TOKEN)
    fs = HfFileSystem(token=HF_TOKEN)

    # Initialize tracking
    job = DownloadTracker()

    # Gather file sizes and compute total
    info = api.repo_info(model_link, files_metadata=True)
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
    all_files = [f for f in api.list_repo_files(model_link) if f in file_sizes]
    misc = [f for f in all_files if not f.endswith(".safetensors")]
    shards = [f for f in all_files if f.endswith(".safetensors")]

    # Download misc sequentially
    for path in misc:
        await asyncio.to_thread(fs.get_file, f"{model_link}/{path}", os.path.join(temp_save_dir, path), callback)
        logger.info(f"Downloaded {path}")

    # Download shards concurrently
    shard_tasks = [(model_link, path) for path in shards]
    await download_files_concurrent(fs, callback, shard_tasks, temp_save_dir)
    logger.info("All shards downloaded")

    # Quantize the model and push into final directory
    try:
        await asyncio.to_thread(convert_hf_mlx, temp_save_dir, final_save_dir)
        shutil.rmtree(temp_save_dir, ignore_errors=True)
    except Exception as e:
        logger.error(f"Failed to convert model: {e}")
        raise
    
    # Wait for ETA monitor to finish
    await eta_task
    logger.info("Download complete")

    return temp_save_dir