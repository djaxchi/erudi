from fastapi import APIRouter, HTTPException
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
from datasets import Dataset
from transformers import Trainer
import torch

router = APIRouter()

@router.post("/train", status_code=200)
async def train_llm_route(payload: TrainingInfo):
    """
    Fine-tune an LLM and update the database after the training is complete.
    """
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    llmLink = llm.link

    # Process the PDF files into a dataset
    dataset = process_pdfs_to_causal_dataset(payload.pdf_files)
    if dataset is None:
        raise HTTPException(status_code=400, detail="Failed to process PDF files into a dataset.")
    
    def update_database_after_training():
        return
    
    background_tasks.add_task(train_and_update)

def train_and_update():
    """
    Trains the model and updates the database after the training is complete.
    """
    try:
        train_llm()

        callback()
    except Exception as e:
        logging.error(f"Error during training or database update: {e}")