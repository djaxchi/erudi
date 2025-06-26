import asyncio
import os
from collections import defaultdict
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.Llm import Llm
from app.schemas.llm_schemas import LLMCreate, LLMResponse

from app.utils.llm_downloader import download_llm
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

@router.get("/llms/{llm_id}/status/stream")
async def stream_status(llm_id: int):
    queue = _status_queues[llm_id]
    async def event_generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ":\n\n"
                else:
                    yield f"data: {msg}\n\n"
                    if msg.startswith("installed") or msg.startswith("error"):
                        break
        finally:
            _status_queues.pop(llm_id, None)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/llms/{llm_id}/download")
async def download_llm_route(
    llm_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")

    queue = _status_queues[llm_id]
    # notify client that download has started
    await queue.put("started")

    def update_database_after_download(model_id: int, save_dir: str):
        # signal 100% progress
        MAIN_LOOP.call_soon_threadsafe(queue.put_nowait, "progress:100%")
        with Session(db.get_bind()) as session:
            old_llm = session.query(Llm).filter(Llm.id == model_id).first()
            if old_llm:
                new_llm = Llm(
                    name=old_llm.name,
                    link=f"{save_dir}/{model_id}",
                    local=True,
                )
                session.add(new_llm)
                session.commit()
                logging.info(f"New LLM created for '{new_llm.name}' with id {new_llm.id}")
        # finally signal installed
        MAIN_LOOP.call_soon_threadsafe(queue.put_nowait, "installed")

    def download_and_update(model_link: str, model_id: int, save_dir: str, callback):
        try:
            download_llm(model_link=model_link, model_id=model_id, save_dir=save_dir)
            callback(model_id, save_dir)
        except Exception as e:
            logging.error(f"Error during download: {e}")
            MAIN_LOOP.call_soon_threadsafe(queue.put_nowait, f"error:{e}")

    background_tasks.add_task(
        download_and_update,
        model_link=llm.link,
        model_id=llm.id,
        save_dir="./data/models",
        callback=update_database_after_download,
    )

    return {"message": f"Download started for LLM '{llm.name}'"}



