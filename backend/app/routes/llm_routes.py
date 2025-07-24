import asyncio
from datetime import datetime
import os
from collections import defaultdict
import shutil

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import SessionLocal, get_db
from ..models.Llm import Llm
from ..schemas.llm_schemas import LLMCreate, LLMResponse
from ..models.DownloadJob import DownloadJobModel
from ..schemas.DownloadJobResponse import DownloadJobResponse

from ..utils.llm_downloader import download_llm
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
            import asyncio
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

@router.get(
    "/downloads/{job_id}/status",
    response_model=DownloadJobResponse,
    status_code=200,
)
def get_download_status(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Fetch the DownloadJobModel by its job_id.
    """
    job = db.query(DownloadJobModel).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    
    if job.status == "failed":
        llm = db.query(Llm).filter(Llm.id == job.local_model_id).first()
        if not llm:
            raise HTTPException(status_code=404, detail="LLM not found")
        db.delete(llm)
        job.local_model_id = -1
        shutil.rmtree(job.local_model_link, ignore_errors=True)
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