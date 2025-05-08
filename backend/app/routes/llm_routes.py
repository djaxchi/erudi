
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.Llm import Llm
from ..schemas.llm_schemas import LLMCreate, LLMResponse
from ..utils.llm_downloader import download_llm

from typing import List

router = APIRouter(prefix="/main_window" )
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

@router.post("/llms/{llm_id}/download")
async def download_llm_route(llm_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Download an LLM by its ID.
    """
    # Fetch the LLM object from the database
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")

    # Start the download in the background
    background_tasks.add_task(download_llm, model_name=llm.link)

    return {"message": f"Download started for LLM '{llm.name}'"}