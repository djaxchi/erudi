from datetime import datetime
import logging
from ..models.Llm import Llm
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
import re
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, DataCollatorForLanguageModeling, BitsAndBytesConfig, Trainer
from peft import get_peft_model, LoraConfig, prepare_model_for_kbit_training
import torch
from datasets import Dataset

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
    
    
    background_tasks.add_task(train_and_update,
        base_model_db=base_model_db,
        dataset_path=dataset_path,
        new_model_name=payload.modelName,
        db=db,
    )

    return {
        "message": "Training started in the background.",
    }
    
    
def train_and_update(base_model_db: Llm, dataset_path: str, new_model_name: str, db: Session, callback):
    """
    Trains the model and updates the database after the training is complete.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:

        logging.info(f"Creating new model entry in the database")
        llm = Llm(name=new_model_name, link='/', local=True)
        db.add(llm)
        db.flush()
        llm.link = f"./data/models/{llm.id}"
        db.commit()
        logging.info(f"New model created")
        
        logging.info(f"BnB config")
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=False,
        )
        logging.info(f"Bnb prepared")

        logging.info(f"Loading model and tokenizer from {base_model_db.link}")
        start = datetime.now()
        model = AutoModelForCausalLM.from_pretrained(
            base_model_db.link,
            torch_dtype=torch.float16,
            quantization_config=bnb_cfg,
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
            remove_columns=["text"],
            num_proc=4,
        )
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False,
            pad_to_multiple_of=8,
        )
        logging.info(f"Dataset loaded from {dataset_path}: train={len(dataset['train'])}, test={len(dataset['test'])}")

        logging
        peft_cfg = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj","v_proj","k_proj","o_proj"],
            lora_dropout=0.1,
            bias="none",
            task_type="CAUSAL_LM",
            modules_to_save=["embed_tokens","lm_head"],
        )

        logging.info(f"Preparing model using kbit")
        model = prepare_model_for_kbit_training(model)
        logging.info(f"model prepared for kbit training")
        logging.info(f"Preparing model for PEFT")
        model = get_peft_model(model, peft_cfg)
        logging.info(f"Model prepared for PEFT")

        logging.info(f"Prepare training args")
        training_args = TrainingArguments(
            output_dir=llm.link,
            overwrite_output_dir=True,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            num_train_epochs=5,
            learning_rate=1e-4,
            weight_decay=0.01,
            warmup_steps=100,
            fp16=True,
            logging_steps=500,
            save_strategy="epoch",
            save_steps=None,
            save_total_limit=1,
            optim="paged_adamw_8bit",
            max_grad_norm=0.3,
            gradient_checkpointing=True,
            dataloader_num_workers=4,
            report_to=[],
            logging_dir=None,
            remove_unused_columns=False,
            cache_dir="./data/models_cache",
        )
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["test"],
            data_collator=data_collator,
        )
        logging.info(f"Training args prepared")

        logging.info("Starting fine-tuning…")
        model.config.use_cache = False
        t0 = datetime.now()
        trainer.train()
        logging.info("Training done in", datetime.now() - t0)

        logging.info("Saving model…")
        model.config.use_cache = True
        merged = model.merge_and_unload()
        merged.save_pretrained(llm.link, safe_serialization=True)
        tokenizer.save_pretrained(llm.link)
        logging.info("Model saved")
        
        return llm
    except Exception as e:
        logging.error(f"Error during training or database update: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error during training or database update: {e}")
        return None