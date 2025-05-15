from datetime import datetime
import logging

from ..models.TrainingJob import TrainingJob
from ..models.Llm import Llm
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends 
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.training_schemas import TrainingInfo
from ..utils.file_processor import process_pdfs_to_causal_dataset
import re
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, DataCollatorForLanguageModeling, BitsAndBytesConfig, Trainer
from peft import get_peft_model, LoraConfig, prepare_model_for_kbit_training
import torch
from datasets import Dataset
from ..database import SessionLocal
from ..schemas.progress_callback import ProgressCallback

router = APIRouter()

@router.get("/training/{llm_id}/status")
def get_training_status(llm_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a training job.
    """
    training_job = db.query(TrainingJob).filter(TrainingJob.llm_id == llm_id).first()
    if not training_job:
        raise HTTPException(status_code=404, detail="Training job not found")
    
    status = training_job.status
    error_message = training_job.error_message
    updated_at = training_job.updated_at

    if status == "failed":
        db.delete(training_job)
        db.delete(db.query(Llm).filter(Llm.id == llm_id).first())
        db.commit()

    return {
        "status": status,
        "status_updated_at": updated_at,
        "error_message": error_message if status == "failed" else None,
        "progress": getattr(training_job, "progress", 0.0),
        "time_elapsed": getattr(training_job, "time_elapsed", 0.0),
        "time_left": getattr(training_job, "time_left", None),
    }

@router.post("/train", status_code=200)
async def train_llm_route(payload: TrainingInfo, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Fine-tune an LLM and update the database after the training is complete.
    """
    
    # Process the PDF files into a dataset
    if not payload.paths:
        raise HTTPException(status_code=400, detail="No files provided.")
    
    if not payload.selectedModel:
        raise HTTPException(status_code=400, detail="Model ID is required.")
    

    try :
        base_model_db = db.query(Llm).filter(Llm.id == payload.selectedModel).first()
        if not base_model_db:
            raise HTTPException(status_code=404, detail="Model not found in the database.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying the database: {e}")
    

    try:
        dataset_path = process_pdfs_to_causal_dataset(payload.paths)
        if dataset_path is None:
            raise HTTPException(status_code=400, detail="Failed to process PDF files into a dataset.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing training files: {e}")
    

    try:
        logging.info(f"creating objects for {payload.modelName}")
        trained_model = Llm(name=payload.modelName, link='/', local=True)
        db.add(trained_model)
        db.flush()
        trained_model.link = f"./data/models/{trained_model.id}"

        training_job = TrainingJob(llm_id=trained_model.id, status="pending")
        db.add(training_job)
        db.commit()
        
        logging.info(f"Objects created for {payload.modelName} with ID {trained_model.id}")
        
        logging.info(f"Starting training background task")
        background_tasks.add_task(train_and_update,
            base_model_db_id=base_model_db.id,
            dataset_path=dataset_path,
            training_job_id=training_job.id,
            trained_model_id=trained_model.id,
        )
        logging.info(f"Training task added to background : {trained_model.id}")

        return {
            "message": "Training started in the background.",
            "llm_in_training_id": trained_model.id,
        }
    
    except Exception as e:
        logging.error(f"Error starting training: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting training: {e}")
    
    
def train_and_update(base_model_db_id: int, dataset_path: str, training_job_id: int = None, trained_model_id: int = None):
    """
    Trains the model and updates the database after the training is complete.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = None
    tokenizer = None
    
    db = SessionLocal()
    try:
        
        base_model_db = db.query(Llm).filter(Llm.id == base_model_db_id).first()
        training_job = db.query(TrainingJob).filter(TrainingJob.id == training_job_id).first()
        trained_model = db.query(Llm).filter(Llm.id == trained_model_id).first()

        if not trained_model:
            logging.error("Trained model not found in background task")
            return
        
        training_job.status = "running"
        training_job.updated_at = datetime.now()
        db.commit()
        logging.info(f"Training job status updated to running for model {trained_model.id}")
        
        if not training_job:
            raise HTTPException(status_code=400, detail="Training job not found.")
        
        if not base_model_db:
            raise HTTPException(status_code=400, detail="Base model not found.")

        logging.info(f"Loading model and tokenizer from {base_model_db.link}")
        start = datetime.now()
        model = AutoModelForCausalLM.from_pretrained(
            base_model_db.link,
            torch_dtype=torch.float16,
            attn_implementation="sdpa",
        ).to(device)
        tokenizer = AutoTokenizer.from_pretrained(base_model_db.link)
        tokenizer.pad_token = tokenizer.eos_token
        logging.info(f"Model and tokenizer loaded in {datetime.now() - start}")

        def tokenize_fn(batch):
            return tokenizer(
                batch["text"],
                truncation=True,
                padding="max_length",
                max_length=512,
            )
        
        logging.info(f"Loading dataset from {dataset_path}")
        with open(dataset_path, 'r', encoding='utf-8') as f:
            text_data = f.read().split('\n')
        text_data = [line for line in text_data if line.strip()]
        dataset_dict = [{"text": line} for line in text_data]
        dataset = Dataset.from_list(dataset_dict)
        dataset = dataset.train_test_split(test_size=0.05, seed=42)
        dataset = dataset.map(
            tokenize_fn,
            batched=True,
            remove_columns=["text"]
        )
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False,
            pad_to_multiple_of=8,
        )
        logging.info(f"Dataset loaded from {dataset_path}: train={len(dataset['train'])}, test={len(dataset['test'])}")

        peft_cfg = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj","v_proj","k_proj","o_proj"],
            lora_dropout=0.1,
            bias="none",
            task_type="CAUSAL_LM",
            modules_to_save=["embed_tokens","lm_head"],
        )

        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(model, peft_cfg)

        logging.info(f"Prepare training args")
        training_args = TrainingArguments(
            output_dir=trained_model.link,
            overwrite_output_dir=True,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            num_train_epochs=5,
            learning_rate=1e-4,
            weight_decay=0.01,
            warmup_steps=100,
            fp16=True,
            logging_steps=20,
            save_strategy="epoch",
            save_steps=None,
            save_total_limit=1,
            optim="paged_adamw_8bit",
            max_grad_norm=0.3,
            gradient_checkpointing=True,
            dataloader_num_workers=4,
            report_to=[],
            logging_dir=trained_model.link+"/logs",
            remove_unused_columns=False,
        )
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["test"],
            data_collator=data_collator,
            callbacks=[ProgressCallback(training_job_id=training_job.id, db_factory=SessionLocal)],
        )
        logging.info(f"Training args prepared")

        logging.info("Starting fine-tuning…")
        model.config.use_cache = False
        t0 = datetime.now()
        trainer.train()
        logging.info(f"Training done in {datetime.now() - t0} seconds")

        logging.info("Saving model…")
        model.config.use_cache = True
        merged = model.merge_and_unload()
        merged.save_pretrained(trained_model.link, safe_serialization=True)
        tokenizer.save_pretrained(trained_model.link)
        logging.info("Model saved")

        training_job.status = "completed"
        training_job.updated_at = datetime.now()
        db.commit()
        logging.info(f"Training job status updated to completed for model {trained_model.id}")
        
        logging.info(f"Training completed successfully for model {trained_model.id}")
        
        return trained_model
    
    except Exception as e:
        logging.error(f"Error during training or database update: {e}")
        
        try:
            if training_job and training_job.id:
                training_job = db.query(TrainingJob).filter(TrainingJob.id == training_job.id).first()
                if training_job:
                    training_job.status = "failed"
                    training_job.updated_at = datetime.now()
                    training_job.error_message = str(e)
                    db.commit()
                logging.info(f"Training job status updated to failed for model {trained_model.id}")
                
            if model:
                del model
            if tokenizer:
                del tokenizer
        except Exception as inner_e:
            logging.error(f"Failed to update training status: {inner_e}")

    finally:
        db.close()
