import asyncio
from datetime import datetime
import os
from collections import defaultdict
import shutil
import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import SessionLocal, get_db
from ..entities.Llm import Llm
from ..llms.schemas import LLMCreate, LLMResponse
from ..entities.DownloadJob import DownloadJobModel
from ..schemas import DownloadJobResponse

from ..llms.services import download_llm
import logging

from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    if db_llm.local == 2:
        raise HTTPException(status_code=400, detail="LLM is currently downloading")
    if db_llm.link and os.path.exists(db_llm.link):
        shutil.rmtree(db_llm.link, ignore_errors=True)
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
    """
    Fetch the DownloadJobModel without its job_id.
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