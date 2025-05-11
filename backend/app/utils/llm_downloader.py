# import os
# from datetime import datetime
# from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
# import torch
# import logging
# import gc

# # Set up logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# HF_TOKEN = "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"

# device = "cuda" if torch.cuda.is_available() else "cpu"
# logging.info(f"Using device: {device}")


# def download_llm(model_name: str, cache_dir: str = "./data/models"):
#     """
#     Downloads an LLM from Hugging Face and stores it in the specified cache directory.

#     Args:
#         model_name (str): The Hugging Face model name or link.
#         cache_dir (str): The directory where the model will be downloaded.

#     Returns:
#         str: The path to the downloaded model.
#     """
#     # Ensure the cache directory exists
#     os.makedirs(cache_dir, exist_ok=True)

#     # Configure quantization
#     bnb_config = BitsAndBytesConfig(
#         load_in_4bit=True,
#         bnb_4bit_quant_type="nf4",
#         bnb_4bit_compute_dtype=torch.float16,
#         bnb_4bit_use_double_quant=False,
#     )

#     logging.info(f"Downloading model '{model_name}' to '{cache_dir}'...")
#     start = datetime.now()

#     # Download the tokenizer
#     AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir,token=HF_TOKEN)

#     # Download the model
#     AutoModelForCausalLM.from_pretrained(
#         model_name,
#         cache_dir=cache_dir,
#         token=HF_TOKEN,
#         quantization_config=bnb_config,
#         torch_dtype=torch.float16,
#         attn_implementation="sdpa",
#         force_download=False
#     )

#     logging.info(f"Model downloaded successfully in {datetime.now() - start}")
    
#     return cache_dir