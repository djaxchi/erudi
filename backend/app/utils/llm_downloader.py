import os
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
import logging
import gc
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HF_TOKEN = "***HF_TOKEN_REMOVED***"

device = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {device}")


def download_llm(model_link: str, model_id: int, save_dir: str = "./data/models", cache_dir: str = "./data/models_cache"):
    """
    Downloads an LLM from Hugging Face and stores it in the specified cache directory.

    Args:
        model_id (str): The Hugging Face model name or link.
        save_dir (str): The directory where the model will be downloaded.

    Returns:
        str: The path to the downloaded model.
    """
    # Ensure the cache directory exists
    os.makedirs(save_dir, exist_ok=True)

    # Configure quantization
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False,
    )

    logging.info(f"Downloading model '{model_id}' to '{save_dir}'...")
    start = datetime.now()

    # Download the tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_link,token=HF_TOKEN, cache_dir=cache_dir)

    # Download the model
    model = AutoModelForCausalLM.from_pretrained(
        model_link,
        token=HF_TOKEN,
        quantization_config=bnb_config,
        torch_dtype=torch.float16,
        attn_implementation="sdpa",
        force_download=False,
        cache_dir=cache_dir
    ).to(device)

    logging.info(f"Model downloaded successfully in {datetime.now() - start}")

    model.save_pretrained(save_dir+"/"+str(model_id))
    tokenizer.save_pretrained(save_dir+"/"+str(model_id))
    logging.info(f"Model and tokenizer saved to '{save_dir}'")

    # Clean up
    del model
    del tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    shutil.rmtree(cache_dir, ignore_errors=True)
    
    return save_dir