import os
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
import logging
import gc

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HF_TOKEN = "***HF_TOKEN_REMOVED***"

device = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {device}")


path = ""
# Configure quantization
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=False,
)

logging.info(f"Downloading model 'mistral' from '{path}'...")
start = datetime.now()

# Download the tokenizer
tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)

# Download the model
model = AutoModelForCausalLM.from_pretrained(
    path,
    local_files_only=True,
    quantization_config=bnb_config,
    torch_dtype=torch.float16,
    attn_implementation="sdpa"
).to(device)

logging.info(f"Model downloaded successfully in {datetime.now() - start}")