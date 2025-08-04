import asyncio
from datetime import datetime
from collections import defaultdict
import os
from pathlib import Path
import shutil
import asyncio
from datetime import datetime, timedelta
import sys
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.Llm import Llm
from app.schemas.llm_schemas import LLMCreate, LLMResponse
from app.database import SessionLocal, get_db
from app.models.DownloadJob import DownloadJobModel
from app.schemas.DownloadJobResponse import DownloadJobResponse

from app.utils.llm_downloader import download_llm
from app.utils.global_variables_util import BASE_PATH
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/main_window")

# Capture the main asyncio event loop at import
MAIN_LOOP = asyncio.get_event_loop()

# Shared status queues per llm_id
_status_queues: dict[int, asyncio.Queue[str]] = defaultdict(lambda: asyncio.Queue())

@router.get("/llms", response_model=List[LLMResponse])
async def get_all_llms(db: Session = Depends(get_db)):
    llms = db.query(Llm).all()
    return llms

@router.get("/llms/local", response_model=List[LLMResponse])
async def get_local_llms(db: Session = Depends(get_db)):
    llms = db.query(Llm).filter(Llm.local == 1).all()
    return llms

@router.get("/llms/remote", response_model=List[LLMResponse])
async def get_remote_llms(db: Session = Depends(get_db)):
    llms = db.query(Llm).filter(Llm.local == 0).all()
    return llms

@router.get("/llms/{llm_id}", response_model=LLMResponse)
async def get_llm_by_id(llm_id: int, db: Session = Depends(get_db)):
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    return llm

@router.post("/llms", response_model=LLMResponse)
async def create_llm(llm: LLMCreate, db: Session = Depends(get_db)):
    model_type = llm.get("type", None)
    if not model_type:
        raise HTTPException(status_code=400, detail="Model type (e.g. 'mistral', 'gemma') is required")
    db_llm = Llm(**llm.dict())
    db.add(db_llm)
    db.commit()
    db.refresh(db_llm)
    return db_llm

@router.put("/llms/{llm_id}", response_model=LLMResponse)
async def update_llm(llm_id: int, llm: LLMCreate, db: Session = Depends(get_db)):
    db_llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not db_llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    for key, value in llm.dict().items():
        setattr(db_llm, key, value)
    db.commit()
    db.refresh(db_llm)
    return db_llm

@router.delete("/llms/{llm_id}")
async def delete_llm(llm_id: int, db: Session = Depends(get_db)):
    db_llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not db_llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    db.delete(db_llm)
    db.commit()
    return {"message": "LLM deleted successfully"}

@router.get("/llms/search", response_model=List[LLMResponse])
async def search_llms(name: str, db: Session = Depends(get_db)):
    llms = db.query(Llm).filter(Llm.name.ilike(f"%{name}%")).all()
    return llms


@router.post(
    "/llms/{llm_id}/download",
    response_model=DownloadJobResponse,
    status_code=200,
)
async def download_llm_route(
    llm_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
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
    )
    db.add(local_llm)
    db.commit()
    db.refresh(local_llm)
    local_llm.link = f"./data/models/{local_llm.id}"
    db.commit()
    logger.info(f"Created local LLM entry: {local_llm.name} - {local_llm.link}")

    # Create persistent DownloadJobModel
    job = DownloadJobModel(
        remote_model_id=llm_id,
        local_model_id=local_llm.id,
        remote_model_link=remote_llm.link,
        local_model_link=local_llm.link,
        status="pending",
        total_bytes=0.0,
        progress=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    def _download_task(model_link: str, model_id: int, save_dir: str, job_id: int):
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
                    save_dir=save_dir,
                    job_id=job_id,
                )
            )
        except Exception as e:
            session = SessionLocal()
            dj = session.query(DownloadJobModel).get(job_id)
            dj.status = "failed"
            dj.error_message = str(e)
            path_to_del = os.path.join(BASE_PATH, dj.local_model_link.lstrip("./"))
            shutil.rmtree(path_to_del, ignore_errors=True)
            dj.local_model_link = ""
            dj.updated_at = datetime.now()
            session.commit()
            session.close()

    # 2) enqueue background
    background_tasks.add_task(
        _download_task,
        remote_llm.link,
        local_llm.id,
        local_llm.link,
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
    """
    Cancel a download job by its job_id.
    """
    job = db.query(DownloadJobModel).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")

    if job.status in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or failed jobs")

    # Mark the job as cancelled
    job.status = "cancelled"
    job.updated_at = datetime.now()
    db.commit()

    # Clean up local model if it exists
    if job.local_model_link:
        # Attention ici à bien supprimer le PATH ABSOLU
        shutil.rmtree(job.local_model_link, ignore_errors=True)
        job.local_model_link = ""
        job.local_model_id = -1

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
    """
    Fetch the DownloadJobModel by its job_id.
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
        path_to_del = os.path.join(BASE_PATH, job.local_model_link.lstrip("./"))
        if os.path.exists(path_to_del):
            shutil.rmtree(path_to_del, ignore_errors=True)
        job.local_model_link = ""
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
    """
    Fetch the DownloadJobModel by its job_id.
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
        path_to_del = os.path.join(BASE_PATH, job.local_model_link.lstrip("./"))
        if os.path.exists(path_to_del):
            shutil.rmtree(path_to_del, ignore_errors=True)
        job.local_model_link = ""
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