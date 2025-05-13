import asyncio
import os
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.Llm import Llm
from ..schemas.llm_schemas import LLMCreate, LLMResponse
import json
from collections import defaultdict
import re

from ..utils.llm_downloader import download_llm
import logging

from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/main_window")

download_progress: dict[int, int] = defaultdict(int)


def _progress_cb(model_id: int, bytes_done: int, bytes_total: int):
    pct = int(bytes_done / bytes_total * 100)
    download_progress[model_id] = pct


@router.get("/llms", response_model=List[LLMResponse])
async def get_all_llms(db: Session = Depends(get_db)):
    """
    Fetch all LLMs (local and remote).
    """
    llms = db.query(Llm).all()
    return llms


@router.get("/llms/local", response_model=List[LLMResponse])
async def get_local_llms(db: Session = Depends(get_db)):
    """
    Fetch all local LLMs.
    """
    llms = db.query(Llm).filter(Llm.local == 1).all()
    return llms


@router.get("/llms/remote", response_model=List[LLMResponse])
async def get_remote_llms(db: Session = Depends(get_db)):
    """
    Fetch all remote LLMs.
    """
    llms = db.query(Llm).filter(Llm.local == 0).all()
    return llms


@router.get("/llms/{llm_id}", response_model=LLMResponse)
async def get_llm_by_id(llm_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single LLM by its ID.
    """
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    return llm


@router.post("/llms", response_model=LLMResponse)
async def create_llm(llm: LLMCreate, db: Session = Depends(get_db)):
    """
    Create a new LLM.
    """
    db_llm = Llm(**llm.dict())
    db.add(db_llm)
    db.commit()
    db.refresh(db_llm)
    return db_llm


@router.put("/llms/{llm_id}", response_model=LLMResponse)
async def update_llm(llm_id: int, llm: LLMCreate, db: Session = Depends(get_db)):
    """
    Update an existing LLM.
    """
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
    """
    Delete an LLM by its ID.
    """
    db_llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not db_llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    db.delete(db_llm)
    db.commit()
    return {"message": "LLM deleted successfully"}


@router.get("/llms/search", response_model=List[LLMResponse])
async def search_llms(name: str, db: Session = Depends(get_db)):
    """
    Search LLMs by name.
    """
    llms = db.query(Llm).filter(Llm.name.ilike(f"%{name}%")).all()
    return llms


@router.get("/llms/{llm_id}/download/stream")
async def stream_download(llm_id: int):
    """
    Runs your existing download script as a subprocess,
    watches its stdout for any “NN%” fragments,
    tracks the highest % seen, and emits that over SSE.
    """
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-u",
        "scripts/download_llm.py",
        str(llm_id),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def event_generator():
        assert proc.stdout is not None
        max_pct = 0
        # read line-by-line as soon as download_llm prints something
        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", "ignore").rstrip()

            # pull out *all* percentages on that line
            found = [int(n) for n in re.findall(r"(\d{1,3})\s*%", line)]
            if found:
                local_max = max(found)
                if local_max > max_pct:
                    max_pct = local_max
                    # push only when our global max increases
                    yield f"data: {json.dumps({'progress': max_pct})}\n\n"

            # (optional) if you still want to stream raw lines, uncomment:
            # yield f"data: {json.dumps({'line': line})}\n\n"

        await proc.wait()
        # make sure we finish at 100%
        if max_pct < 100:
            yield f"data: {json.dumps({'progress': 100})}\n\n"
        yield f"data: {json.dumps({'status': 'complete'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/llms/{llm_id}/download")
async def download_llm_route(
    llm_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Download an LLM by its ID and update the database after the download is complete.
    """
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")

    def update_database_after_download(model_id: int, save_dir: str):
        with Session(db.get_bind()) as session:
            old_llm = session.query(Llm).filter(Llm.id == llm_id).first()
            if old_llm:
                new_llm = Llm(
                    name=old_llm.name,
                    link=save_dir + "/" + str(model_id),
                    local=True,
                )
                session.add(new_llm)
                session.commit()
                logging.info(
                    f"New LLM created for '{new_llm.name}' with id {new_llm.id}"
                )

    background_tasks.add_task(
        download_and_update,
        model_link=llm.link,
        model_id=llm.id,
        save_dir="./data/models",
        callback=update_database_after_download,
    )

    return {"message": f"Download started for LLM '{llm.name}'"}


def download_and_update(model_link: str, model_id: int, save_dir: str, callback):
    """
    Downloads the model and updates the database after the download is complete.

    Args:
        model_name (str): The Hugging Face model name or link.
        save_dir (str): The directory where the model will be downloaded.
        callback (function): A function to call after the download is complete.
    """
    try:
        download_llm(  # ▼ inject the callback
            model_link=model_link,
            model_id=model_id,
            save_dir=save_dir,
            progress_callback=lambda done, total: _progress_cb(model_id, done, total),
        )
        callback(model_id, save_dir)
    except Exception as e:
        logging.error(f"Error during download or database update: {e}")
