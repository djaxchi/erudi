import re
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, DataCollatorForLanguageModeling, BitsAndBytesConfig
from peft import get_peft_model, LoraConfig, prepare_model_for_kbit_training
import torch

# === TEXT CLEANING ===
def clean_text(text):
    """Remove extra whitespace from text."""
    return re.sub(r"\s+", " ", text).strip()

def remove_invalid_unicode(text):
    """Remove invalid unicode characters from text."""
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")

# === CHUNKING ===
def chunk_text(text, chunk_size=512, overlap=50):
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        segment = " ".join(words[i : i + chunk_size]).strip()
        if len(segment) > 50:
            chunks.append({"text": segment})
        i += chunk_size - overlap
    return chunks

# === TOKENIZATION ===
def tokenize_fn(tokenizer, max_length=512):
    """Return a function to tokenize a batch for HuggingFace Datasets."""
    def _tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )
    return _tokenize

# === MODEL & TOKENIZER LOADING ===
def get_model_and_tokenizer(model_name, use_bnb=False, hf_token=None):
    """Load model and tokenizer, optionally with BitsAndBytes 4bit quantization."""
    if use_bnb:
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=False,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            token=hf_token,
            device_map="auto",
            quantization_config=bnb_cfg,
            torch_dtype=torch.float16,
            attn_implementation="sdpa"
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            token=hf_token,
            device_map="auto",
            torch_dtype=torch.float16,
            attn_implementation="sdpa"
        )
    tokenizer = AutoTokenizer.from_pretrained(model_name, token=hf_token)
    tokenizer.pad_token = tokenizer.eos_token
    return model, tokenizer

# === PEFT CONFIG ===
def get_peft_model_config():
    """Return a default LoRAConfig for PEFT."""
    return LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj","v_proj","k_proj","o_proj"],
        lora_dropout=0.1,
        bias="none",
        task_type="CAUSAL_LM",
        modules_to_save=["embed_tokens","lm_head"],
    )

# === TRAINING ARGUMENTS ===
def get_training_args(output_dir="mistral-finetuned", batch_size=1, epochs=5, learning_rate=1e-4, logging_steps=500):
    """Return TrainingArguments for HuggingFace Trainer."""
    return TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        weight_decay=0.01,
        warmup_steps=100,
        fp16=True,
        logging_steps=logging_steps,
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
    )

# === DATA COLLATOR ===
def get_data_collator(tokenizer):
    return DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
        pad_to_multiple_of=8,
    )

# === TRAINING FUNCTION ===
def train_llm(model, tokenizer, dataset, training_args, peft_config):
    """Train the model using HuggingFace Trainer."""
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, peft_config)
    data_collator = get_data_collator(tokenizer)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
        tokenizer=tokenizer,
    )
    trainer.train()
