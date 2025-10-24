"""
Inference utilities for embeddings and model services.

Note: Prompt building and KB utilities have been moved to:
- src.utils.prompt_utils (prompt building and strategies)
- src.utils.kb_utils (knowledge base retrieval)
"""
import os

from backend.src.core.config import CACHE_DIR
from src.core.logging import logger


class EmbedderService:
    """Singleton service for managing the sentence transformer embedder.
    
    This service ensures only one instance of the embedder is loaded in memory
    and provides centralized access to it across the application.
    """
    _instance = None
    
    def __init__(self):
        raise RuntimeError("Use get_embedder() instead of instantiating")
    
    @classmethod
    def get_embedder(cls):
        """Get or create the embedder instance.
        
        Returns:
            SentenceTransformer: The singleton embedder instance.
        """
        from sentence_transformers import SentenceTransformer
        if cls._instance is None:
            logger.info("Loading the Embedder via EmbedderService")
            os.makedirs(CACHE_DIR, exist_ok=True)
            cls._instance = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                cache_folder=CACHE_DIR,
            )
            logger.info("Embedder loaded")
        return cls._instance
    
    @classmethod
    def cleanup(cls) -> None:
        """Release the embedder instance and free memory."""
        if cls._instance is not None:
            del cls._instance
            cls._instance = None
            logger.info("Embedder cleaned up")


# Re-export commonly used functions from new locations for backward compatibility
from src.utils.prompt_utils import build_system_prompt, get_prompting_strategy
from src.utils.kb_utils import get_relevant_texts_from_kb

__all__ = [
    'EmbedderService',
    'build_system_prompt',
    'get_prompting_strategy',
    'get_relevant_texts_from_kb',
]
