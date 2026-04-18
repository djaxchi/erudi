"""REST API endpoints for LLM fine-tuning orchestration (STUB - Under Development).

This module will orchestrate fine-tuning workflows for local LLMs using LoRA/QLoRA adapters.
Currently implements status polling endpoint only. Full training pipeline is commented out
pending multi-engine training adapter implementation.

Planned Architecture:
    ┌──────────────┐
    │ User uploads │
    │ training PDFs│
    └───────┬──────┘
            │ (1) POST /training/train → Create TrainingJob
            ↓
    ┌──────────────┐
    │ Process PDFs │ ← process_pdfs_to_causal_dataset()
    │ to causal    │   (extract text, chunk, format for CLM)
    │ dataset      │
    └───────┬──────┘
            │ (2) Background task: train_and_update()
            ↓
    ┌──────────────┐
    │ Load base    │ ← AutoModelForCausalLM + PEFT LoRA
    │ model + LoRA │   (quantized 4-bit for memory efficiency)
    └───────┬──────┘
            │ (3) Train with HuggingFace Trainer
            ↓
    ┌──────────────┐
    │ Poll status  │ ← GET /training/{llm_id}/status
    │ via TrainJob │   (progress, time_left, error_message)
    └──────────────┘

Current Status:
    - Status polling: ✅ IMPLEMENTED
    - Training pipeline: ⏸️ STUBBED (commented out)
    - Multi-engine adapters: 🚧 PENDING

TODO:
    - Add training methods to BaseEngine interface.
    - Implement MLX_Engine.train() for Apple Silicon LoRA.
    - Implement CUDA_Engine.train() for NVIDIA LoRA.
    - Uncomment and adapt train_llm_route() endpoint.

Endpoints:
    - GET /training/{llm_id}/status → Poll training job progress.
    - POST /training/train → (COMMENTED OUT) Start fine-tuning job.

Example:
    GET /training/42/status
    Response: {
        "status": "running",
        "progress": 65.0,
        "time_elapsed": 120.5,
        "time_left": 60.2,
        "error_message": null
    }
"""
# TODO AJOUTER LES BAILS DE TRAINING DANS LES ENGINES POUR ADAPTER ET DECOMMENTER



import shutil

from sqlalchemy.orm import Session
from src.database.core import get_db

from fastapi import Depends, APIRouter

from src.entities.TrainingJob import TrainingJob
from src.entities.Llm import Llm

from src.core.exceptions import DatabaseException


router = APIRouter(prefix="/training", tags=["training"])


@router.get("/training/{llm_id}/status")
def get_training_status(llm_id: int, db: Session = Depends(get_db)):
    """Poll training job status with progress metrics and automatic cleanup on failure.

    Queries TrainingJob for the given LLM ID, returns status/progress/timing. If status="failed",
    automatically deletes the temp LLM entry and cleans up model files.

    Args:
        llm_id: Database ID of the LLM being trained.
        db: Database session injected by FastAPI.

    Returns:
        dict: {
            "status": str,  # pending/running/completed/failed
            "status_updated_at": datetime,
            "error_message": str | None,
            "progress": float (0-100),
            "time_elapsed": float (seconds),
            "time_left": float | None (seconds)
        }

    Raises:
        DatabaseException: If training job not found for given llm_id.

    Example:
        GET /training/42/status
        Response: {
            "status": "running",
            "progress": 65.0,
            "time_elapsed": 120.5,
            "time_left": 60.2,
            "error_message": null
        }
    """
    training_job = db.query(TrainingJob).filter(TrainingJob.llm_id == llm_id).first()
    if not training_job:
        raise DatabaseException(f"Training job not found for LLM {llm_id}")
    
    status = training_job.status
    error_message = training_job.error_message
    updated_at = training_job.updated_at

    if status == "failed":
        llm = db.query(Llm).filter(Llm.id == llm_id).first()
        if llm:
            if not error_message:
                llm.error_message = "An unknown error occurred during training."
            shutil.rmtree(llm.link, ignore_errors=True)
            db.delete(llm)
        db.commit()

    return {
        "status": status,
        "status_updated_at": updated_at,
        "error_message": error_message if status == "failed" else None,
        "progress": getattr(training_job, "progress", 0.0),
        "time_elapsed": getattr(training_job, "time_elapsed", 0.0),
        "time_left": getattr(training_job, "time_left", None),
    }

# @router.post("/train", status_code=200)
# async def train_llm_route(payload: TrainingInfo, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
#     """
#     Fine-tune an LLM and update the database after the training is complete.
#     """
#     def clear_memory():
#         """Clear GPU memory and cache for macOS"""
#         if torch.backends.mps.is_available():
#             torch.mps.empty_cache()
#             torch.mps.synchronize()
#         gc.collect()
#     clear_memory()
    
#     # Process the PDF files into a dataset
#     if not payload.paths:
#         raise HTTPException(status_code=400, detail="No files provided.")
    
#     if not payload.selectedModel:
#         raise HTTPException(status_code=400, detail="Model ID is required.")
    

#     try :
#         base_model_db = db.query(Llm).filter(Llm.id == payload.selectedModel).first()
#         if not base_model_db:
#             raise HTTPException(status_code=404, detail="Model not found in the database.")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error querying the database: {e}")
    

#     try:
#         dataset_path = process_pdfs_to_causal_dataset(payload.paths)
#         if dataset_path is None:
#             raise HTTPException(status_code=400, detail="Failed to process PDF files into a dataset.")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error processing training files: {e}")
    

#     try:

#         """
#                 # Check if the user has reached the limit of 5 completed training
#                 completed_jobs = db.query(TrainingJob).filter(TrainingJob.status == "completed").count()
#                 if completed_jobs >= 5:
#                     raise HTTPException(status_code=400, detail="You can only train 5 models using Erudi's Community Edition.")
# """


#         logger.info(f"creating objects for {payload.modelName}")
#         trained_model = Llm(name=payload.modelName, link='/', local=False, type=base_model_db.type)
#         db.add(trained_model)
#         db.flush()
#         # Use config.LLM_DIR for model storage
#         trained_model.link = str(config.LLM_DIR / str(trained_model.id))

#         training_job = TrainingJob(llm_id=trained_model.id, status="pending")
#         db.add(training_job)
#         db.commit()
        
#         logger.info(f"Objects created for {payload.modelName} with ID {trained_model.id}")
        
#         logger.info(f"Starting training background task")
#         background_tasks.add_task(train_and_update,
#             base_model_db_id=base_model_db.id,
#             dataset_path=dataset_path,
#             training_job_id=training_job.id,
#             trained_model_id=trained_model.id,
#         )
#         logger.info(f"Training task added to background : {trained_model.id}")

#         return {
#             "message": "Training started in the background.",
#             "llm_in_training_id": trained_model.id,
#         }
    
#     except Exception as e:
#         logger.error(f"Error starting training: {e}")
#         raise HTTPException(status_code=500, detail=f"Error starting training: {e}")
    
    
# def train_and_update(base_model_db_id: int, dataset_path: str, training_job_id: int = None, trained_model_id: int = None):
#     """
#     Trains the model and updates the database after the training is complete.
#     """

#     from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, DataCollatorForLanguageModeling, Trainer
#     from peft import get_peft_model, LoraConfig, prepare_model_for_kbit_training
#     import torch
#     from datasets import Dataset

#     flash_attn_impl = False
#     device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
#     model = None
#     tokenizer = None
    
#     db = SessionLocal()
#     try:
#         training_job = db.query(TrainingJob).filter(TrainingJob.id == training_job_id).first()
#     except Exception as e:
#         logger.error(f"Error finding in db the training job: {e}")
#         db.close()
#         raise HTTPException(status_code=500, detail=f"Error finding training job in database: {e}")
#     try:
#         base_model_db = db.query(Llm).filter(Llm.id == base_model_db_id).first()
#     except Exception as e:
#         logger.error(f"Error finding in db the model to be trained: {e}")
#         db.close()
#         raise HTTPException(status_code=500, detail=f"Error finding base model in database: {e}")
#     try:
#         trained_model = db.query(Llm).filter(Llm.id == trained_model_id).first()
#     except Exception as e:
#         logger.error(f"Error finding in db the new trained model: {e}")
#         db.close()
#         raise HTTPException(status_code=500, detail=f"Error finding trained model in database: {e}")
    
#     try:
#         if not trained_model:
#             logger.error("Trained model not found in background task")
#             raise HTTPException(status_code=400, detail="Trained model not found.")
#         if not training_job:
#             logger.error("Training job not found in background task")
#             raise HTTPException(status_code=400, detail="Training job not found.")
#         if not base_model_db:
#             logger.error("Base model not found in background task")
#             raise HTTPException(status_code=400, detail="Base model not found.")

#         training_job.status = "running"
#         training_job.updated_at = datetime.now()
#         db.commit()
#         logger.info(f"Training job status updated to running for model {trained_model.id}")
        
#         logger.info(f"Loading model and tokenizer from {base_model_db.link}")
#         start = datetime.now()
        
#         # Nettoyage de la mémoire avant le chargement du modèle
#         clear_memory()

#         model = AutoModelForCausalLM.from_pretrained(
#             base_model_db.link,
#             quantization_config=None,
#             torch_dtype=torch.float16,
#             attn_implementation=None,
#             low_cpu_mem_usage=True,
#             device_map="auto",
#             max_memory={0: "5GB"}, 
#         )
        
#         tokenizer = AutoTokenizer.from_pretrained(base_model_db.link)
#         tokenizer.pad_token = tokenizer.eos_token
#         logger.info(f"Model and tokenizer loaded in {datetime.now() - start}")

#         def tokenize_fn(batch):
#             return tokenizer(
#                 batch["text"],
#                 truncation=True,
#                 padding="max_length",
#                 max_length=128,
#             )
        
#         logger.info(f"Loading dataset from {dataset_path}")
#         with open(dataset_path, 'r', encoding='utf-8') as f:
#             text_data = f.read().split('\n')
#         text_data = [line for line in text_data if line.strip()]
#         dataset_dict = [{"text": line} for line in text_data]
#         dataset = Dataset.from_list(dataset_dict)
#         dataset = dataset.train_test_split(test_size=0.01, seed=42)
        
#         dataset = dataset.map(
#             tokenize_fn,
#             batched=True,
#             remove_columns=["text"]
#         )
#         data_collator = DataCollatorForLanguageModeling(
#             tokenizer=tokenizer,
#             mlm=False,
#             pad_to_multiple_of=8,
#         )
#         logger.info(f"Dataset loaded from {dataset_path}: train={len(dataset['train'])}, test={len(dataset['test'])}")

#         peft_cfg = LoraConfig(
#             r=4,
#             lora_alpha=8,
#             target_modules= ["q_proj", "v_proj", "k_proj", "o_proj"] if base_model_db.type == "mistral" else ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
#             lora_dropout=0.0,
#             bias="none",
#             task_type="CAUSAL_LM",
#             modules_to_save=[],
#         )
#         model = prepare_model_for_kbit_training(model)
#         model = get_peft_model(model, peft_cfg)

#         logger.info(f"Prepare training args")
#         training_args = TrainingArguments(
#             output_dir=trained_model.link,
#             overwrite_output_dir=True,
#             per_device_train_batch_size=1,
#             gradient_accumulation_steps=1,
#             num_train_epochs=5,
#             learning_rate=5e-5,
#             weight_decay=0.0,
#             warmup_steps=0,
#             fp16=False,
#             logging_steps=5,
#             save_strategy="no",
#             save_steps=None,
#             save_total_limit=1,
#             optim="adamw_torch",
#             max_grad_norm=1.0,
#             gradient_checkpointing=False,
#             dataloader_num_workers=0,
#             logging_dir=None,
#             remove_unused_columns=True,
#             dataloader_pin_memory=False,
#             eval_strategy="no",
#             report_to="none",
#         )
#         trainer = Trainer(
#             model=model,
#             args=training_args,
#             train_dataset=dataset["train"],
#             eval_dataset=None,
#             data_collator=data_collator,
#             callbacks=[TrainingProgressCallback(training_job_id=training_job.id, db_factory=SessionLocal)],

#         )
#         logger.info(f"Training args prepared")

#         logger.info("Starting fine-tuning…")
#         model.config.use_cache = False
#         t0 = datetime.now()
#         trainer.train()
#         logger.info(f"Training done in {datetime.now() - t0} seconds")

#         logger.info("Saving model…")
#         model.config.use_cache = True
#         merged = model.merge_and_unload()
#         merged.save_pretrained(trained_model.link, safe_serialization=True)
#         tokenizer.save_pretrained(trained_model.link)
#         logger.info("Model saved")

#         training_job.status = "completed"
#         training_job.updated_at = datetime.now()
#         trained_model.local = True
#         db.commit()
#         logger.info(f"Training job status updated to completed for model {trained_model.id}")
        
#         logger.info(f"Training completed successfully for model {trained_model.id}")
        
#         return trained_model
    
#     except Exception as e:
#         logger.error(f"Error during training or database update: {e}")
        
#         try:
#             if training_job:
#                 training_job.status = "failed"
#                 training_job.updated_at = datetime.now()
#                 training_job.error_message = str(e)
#                 if trained_model:
#                     shutil.rmtree(trained_model.link, ignore_errors=True)
#                     db.delete(trained_model)
#                 db.commit()
#             logger.info(f"Training job status updated to failed for model {trained_model.id}")
                
#             torch.backends.mps.empty_cache()
#         except Exception as inner_e:
#             logger.error(f"Failed to update training status: {inner_e}")

#     finally:
#         db.close()
#         clear_memory()


