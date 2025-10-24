# TO COMPLETE WITH BUILDTIME VARS


from dotenv import load_dotenv
import os
from typing import Optional, Type
from pathlib import Path
from src.engines.base_engine import BaseEngine

from huggingface_hub import HfApi

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN", None)
ROOT_DIR = Path(__file__).resolve().parents[2]
INDEXES_DIR = ROOT_DIR / "data" / "indexes"
LLM_DIR = ROOT_DIR / "data" / "models"
CACHE_DIR = ROOT_DIR / "data" / "models_cache"
LOG_DIR = ROOT_DIR / "logs"
db_dir = ROOT_DIR / "data"
db_dir.mkdir(parents=True, exist_ok=True)
db_path = db_dir / "erudi.db"
DATABASE_URL = f"sqlite:///{db_path}"
INDEXES_DIR.mkdir(parents=True, exist_ok=True)
LLM_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

HF_API = HfApi(token=HF_TOKEN)

LLM_Engine : Optional[Type[BaseEngine]] = None # It is defined in the lifespan at FastAPI init.