"""Global application configuration and environment management.

This module centralizes all configuration constants, environment variables,
and directory paths used across the Erudi  It ensures consistent
path resolution and provides a single source of truth for deployment settings.

Configuration Categories:
    - **Authentication**: HuggingFace token for model downloads
    - **Directories**: Data storage, model cache, logs, vector indexes
    - **Database**: SQLite connection string
    - **Engine**: Runtime LLM engine instance (MLX/CUDA/CPU)

Directory Structure:
    ::

        backend/
        ├── data/
        │   ├── erudi.db              # SQLite database
        │   ├── indexes/              # FAISS vector indexes
        │   ├── models/               # Quantized models (MLX/GGUF)
        │   └── models_cache/         # HuggingFace download cache
        └── logs/                     # Structured application logs

Environment Variables:
    HF_TOKEN (optional):
        HuggingFace API token for downloading gated models.
        If not set, only public models are accessible.

        Example in .env::

            HF_TOKEN=***HF_TOKEN_REMOVED***

Global State:
    LLM_Engine:
        Runtime engine instance initialized during FastAPI lifespan startup.
        Set by BaseEngine.get_engine() based on platform detection.
        Type is Optional[Type[BaseEngine]] before initialization.

Example:
    Access configuration in application code::

        from src.core import config

        # Use paths
        model_path = config.LLM_DIR / "Llama-3-8B"
        index_path = config.INDEXES_DIR / "kb_123.index"

        # Check HuggingFace authentication
        if config.HF_TOKEN:
            config.HF_API.whoami()  # Verify token validity

        # Use engine (after lifespan startup)
        async for token in config.LLM_Engine.generate_stream(prompt, params):
            yield token

Note:
    All directories are created automatically at module import time.
    Do not manually modify LLM_Engine; it is managed by the lifespan context.

Warning:
    Changing ROOT_DIR after import will not update derived paths (LLM_DIR,
    CACHE_DIR, etc.). Ensure paths are configured before first import.
"""

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
TRAINING_DATASETS_DIR = ROOT_DIR / "data" / "training_datasets"
LOG_DIR = ROOT_DIR / "logs"
db_dir = ROOT_DIR / "data"
db_dir.mkdir(parents=True, exist_ok=True)
db_path = db_dir / "erudi.db"
DATABASE_URL = f"sqlite:///{db_path}"
INDEXES_DIR.mkdir(parents=True, exist_ok=True)
LLM_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TRAINING_DATASETS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Lazy-loaded HuggingFace API client
_HF_API: Optional[HfApi] = None

def get_hf_api() -> HfApi:
    """Get or initialize HuggingFace API client (lazy-loaded singleton).
    
    Provides thread-safe lazy initialization of HfApi client. The client is
    created only when first requested, avoiding unnecessary initialization
    during imports or when working offline.
    
    Returns:
        HfApi: Configured HuggingFace API client with authentication token.
    
    Note:
        Thread-safe through Python's GIL. Multiple calls return same instance.
        Token is loaded from HF_TOKEN environment variable.
    
    Example:
        >>> from src.core import config
        >>> api = config.get_hf_api()
        >>> models = api.list_models(search="gemma")
    """
    global _HF_API
    if _HF_API is None:
        _HF_API = HfApi(token=HF_TOKEN)
    return _HF_API

LLM_Engine : Optional[Type[BaseEngine]] = None # It is defined in the lifespan at FastAPI init.