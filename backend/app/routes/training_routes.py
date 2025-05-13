import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends 
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.training_schemas import TrainingInfo
from ..utils.file_processor import process_pdfs_to_causal_dataset
from ..utils.training_utils import (
    get_model_and_tokenizer,
    get_peft_model_config,
    get_training_args,
    get_data_collator,
    tokenize_fn,
    train_llm,
)

router = APIRouter()

@router.post("/train", status_code=200)
async def train_llm_route(payload: TrainingInfo, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Fine-tune an LLM and update the database after the training is complete.
    """
    
    # Process the PDF files into a dataset
    if not payload.paths:
        raise HTTPException(status_code=400, detail="No PDF files provided.")
    
    if not payload.selectedModel:
        raise HTTPException(status_code=400, detail="Model ID is required.")
    
    try:
        dataset_path = process_pdfs_to_causal_dataset(payload.paths)
        if dataset_path is None:
            raise HTTPException(status_code=400, detail="Failed to process PDF files into a dataset.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing training files: {e}")
    
    return {"message": "[TEST] Dataset created successfully", "dataset_path": dataset_path}

    def update_database_after_training():
        return
    
    background_tasks.add_task(train_and_update)

def train_and_update():
    """
    Trains the model and updates the database after the training is complete.
    """
    return
    try:
        train_llm()

        callback()
    except Exception as e:
        logging.error(f"Error during training or database update: {e}")