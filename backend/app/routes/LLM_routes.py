
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.LLM import LLM
from ..schemas.LLM import LLMCreate, LLMResponse

from typing import List
# create a basic route that creates a local model to test the database
router = APIRouter(prefix="/api", tags=["LLM"])
@router.post("/main_window/local-models", response_model=LLMResponse)
async def create_local_model(model: LLMCreate, db: Session = Depends(get_db)):
    db_model = LLM(**model.dict())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model
