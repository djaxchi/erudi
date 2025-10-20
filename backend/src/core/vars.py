# TO COMPLETE WITH BUILDTIME VARS


from dotenv import load_dotenv
import os
from typing import Optional, Type
from src.engines.base_engine import BaseEngine

from huggingface_hub import HfApi

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN", None)
INDEXES_DIR = os.getenv("INDEXES_DIR", None)
CACHE_DIR = os.getenv("CACHE_DIR", None)
if not HF_TOKEN or not INDEXES_DIR or not CACHE_DIR :
    raise Exception("PLEASE ENTER ALL THE NEEDED ENV VARS IN THE .env FILE")

HF_API = HfApi(token=HF_TOKEN)

LLM_Engine : Optional[Type[BaseEngine]] = None # It is defined in the lifespan at FastAPI init.