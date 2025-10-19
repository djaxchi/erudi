# TO COMPLETE WITH BUILDTIME VARS


from dotenv import load_dotenv
import os
from typing import Optional, Type
from src.engines.base_engine import BaseEngine

from huggingface_hub import HfApi

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
INDEXES_DIR = os.getenv("INDEXES_DIR", "")

HF_API = HfApi(token=HF_TOKEN)

LLM_Engine : Optional[Type[BaseEngine]] = None # It is defined in the lifespan at FastAPI init.