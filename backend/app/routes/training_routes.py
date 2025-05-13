from fastapi import APIRouter, HTTPException
from ..schemas.training_schemas import TrainingInfo
from ..utils.file_processor import process_pdfs_to_causal_dataset
from ..utils.training_utils import (
    get_model_and_tokenizer,
    get_peft_model_config,
    get_training_args,
    get_data_collator,
    tokenize_fn,
)
from datasets import Dataset
from transformers import Trainer
import torch

router = APIRouter()

@router.post("/train", status_code=200)
async def train_llm(payload: TrainingInfo):
    """
    Endpoint for training a model.
    """
    try:

        dataset = process_pdfs_to_causal_dataset(payload.paths)

        dataset = dataset.train_test_split(test_size=0.05, seed=42)

        model_name = payload.selectedModel
        model, tokenizer = get_model_and_tokenizer(model_name, use_bnb=False)

        tokenized_dataset = dataset.map(
            tokenize_fn(tokenizer, max_length=512),
            batched=True,
            remove_columns=["text"],
            num_proc=4,
        )

        peft_cfg = get_peft_model_config()
        model = get_peft_model(model, peft_cfg)

        training_args = get_training_args(output_dir=payload.modelName)
        data_collator = get_data_collator(tokenizer)

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_dataset["train"],
            eval_dataset=tokenized_dataset["test"],
            data_collator=data_collator,
        )

        # 8. Train
        model.config.use_cache = False
        trainer.train()
        model.config.use_cache = True

        # 9. Save model and tokenizer
        merged = model.merge_and_unload()
        merged.save_pretrained(payload.modelName, safe_serialization=True)
        tokenizer.save_pretrained(payload.modelName)

        return {"message": f"Model fine-tuned and saved to {payload.modelName}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")