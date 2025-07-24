import threading
from typing import Callable, Optional
import shutil
import logging
import gc
from datetime import datetime

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from huggingface_hub import HfApi, hf_hub_download
from dotenv import load_dotenv

import asyncio
import time
import os
from datetime import datetime
from threading import Lock

from huggingface_hub import HfApi, HfFileSystem
from fsspec.callbacks import Callback  # ← le callback attendu par get_file

from sqlalchemy.orm import Session
from ..models.DownloadJob import DownloadJobModel
from ..database import SessionLocal




load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

device = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {device}")

FILES_TO_EXCLUDE = ["consolidated.safetensors"]

class DownloadJob:
    """Suit la progression globale d'un téléchargement multi-fichiers concurrent,
    et estime dynamiquement le temps restant (ETA)."""
    def __init__(self):
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.eta_seconds = None
        self._lock = Lock()
        logging.info("DownloadJob initialized")

    def update(self, bytes_downloaded: int):
        """
        Met à jour le nombre d'octets téléchargés.
        Doit être appelé à chaque chunk reçu.
        """
        with self._lock:
            self.downloaded_bytes += bytes_downloaded

    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100

    def __str__(self):
        base = (f"Download progress: {self.percent:.2f}% "
                f"({self.downloaded_bytes}/{self.total_bytes} bytes)")
        if self.eta_seconds is not None:
            base += f" | ETA: {self.eta_seconds:.2f}s"
        return base

    async def monitor_eta(self, interval: float = 20.0):
        """
        Périodiquement (toutes les `interval` secondes), calcule et stocke
        l'estimation du temps restant en secondes, basé sur la vitesse actuelle.
        """
        logging.info("Starting ETA monitoring")
        last_time = time.time()
        last_downloaded = 0
        while True:
            await asyncio.sleep(interval)
            with self._lock:
                current = self.downloaded_bytes
                total = self.total_bytes
            if current >= total:
                break

            current_time = time.time()
            delta_bytes = current - last_downloaded
            delta_time = current_time - last_time

            if delta_time > 0 and delta_bytes > 0:
                rate = delta_bytes / delta_time
                remaining = total - current
                self.eta_seconds = remaining / rate
                elapsed = current_time - last_time
                logging.info(f"Estimated time elapsed: {elapsed} / {self.eta_seconds:.2f} estimated total seconds")
            else:
                logging.info("Not enough data to estimate ETA")

            last_time = current_time
            last_downloaded = current
        logging.info("ETA monitoring complete")

def make_callback(job: DownloadJob):
    def after_chunk(size, value, **kwargs):
        job.update(value - job.downloaded_bytes)

    return Callback(size=job.total_bytes, hooks={"transfer-chunk": after_chunk})


def update_db_with_progress(job: DownloadJob, job_id: int):
    """
    *Only updates* an existing DownloadJobModel row.
    """
    session = SessionLocal()
    dbj = session.query(DownloadJobModel).get(job_id)
    start = datetime.utcnow()
    try:
        while job.percent < 100.0:
            time.sleep(1)
            dbj.total_bytes = job.total_bytes
            dbj.progress = job.percent
            dbj.total_time_elapsed = (datetime.utcnow() - start).total_seconds()
            dbj.time_left = job.eta_seconds or 0.0
            session.commit()
        dbj.progress = 100.0
        dbj.status = "completed"
        session.commit()
    except Exception as e:
        dbj.status = "failed"
        dbj.error_message = str(e)
        session.commit()
    finally:
        session.close()


async def download_files_concurrent(hf_file_system: HfFileSystem, callback: Callback, tasks: list, local_dir: str):
    """
    Télécharge en parallèle une liste de (repo_id, path) via threads.
    'tasks' est une liste de tuples (repo_id, path).
    """
    loop = asyncio.get_running_loop()
    jobs = []
    for repo_id, path in tasks:
        remote = f"{repo_id}/{path}"
        local_path = os.path.join(local_dir, path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        logging.info(f"Scheduling download: {path}")
        jobs.append(loop.run_in_executor(
            None,
            hf_file_system.get_file,
            remote,
            local_path,
            callback
        ))
    await asyncio.gather(*jobs)


async def download_llm(
        model_link: str,
        model_id: str,
        save_dir: str = "./data/models",
        job_id: Optional[int] = None,
        )->str:
    
    # Prépare dossier
    save_dir = os.path.join(save_dir, model_id)
    os.makedirs(save_dir, exist_ok=True)
    logging.info(f"Starting download of repo: {model_link} → {save_dir}")

    # Init API et FS avec token
    api = HfApi(token=HF_TOKEN)
    fs = HfFileSystem(token=HF_TOKEN)

    job = DownloadJob()

    # 1. Récupération des tailles et calcul total
    info = api.repo_info(model_link, files_metadata=True)
    file_sizes = {s.rfilename: s.size for s in info.siblings if s.size}
    file_sizes = {f: size for f, size in file_sizes.items() if f not in FILES_TO_EXCLUDE}
    job.total_bytes = sum(file_sizes.values())
    logging.info(f"Total to download: {job.total_bytes} bytes ({job.total_bytes/1024**2:.2f} MB)")
    
    # 2. Créer callback partagé
    callback = make_callback(job)
    callback.set_size(job.total_bytes)

    # 3. Séparer les tâches : misc puis shards
    all_files = [f for f in api.list_repo_files(model_link) if f in file_sizes]
    misc = [f for f in all_files if not f.endswith(".safetensors")]
    shards = [f for f in all_files if f.endswith(".safetensors")]

    logging.info(f"Phases: misc={len(misc)}, shards={len(shards)} files")

    if job_id is not None:
        threading.Thread(
            target=update_db_with_progress,
            args=(job, job_id),
            daemon=True
        ).start()
    eta_task = asyncio.create_task(job.monitor_eta(interval=20.0))

    # 5. Phase 1: misc séquentiel
    for path in misc:
        await asyncio.to_thread(fs.get_file, f"{model_link}/{path}", os.path.join(save_dir, path), callback)
        logging.info(f"Loaded misc: {path}")

    # 6. Phase 2: shards en parallèle
    tasks_shards = [(model_link, f) for f in shards]
    await download_files_concurrent(fs, callback, tasks_shards, save_dir)
    logging.info("Shards downloaded.")

    # 7. Attendre la fin des suivis
    await eta_task

    logging.info("All files downloaded.")

    return save_dir

