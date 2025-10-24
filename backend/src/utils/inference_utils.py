"""Inference Utilities for Embeddings and Backward Compatibility.

This module provides the EmbedderService singleton for managing the sentence
transformer embedder used in knowledge base (RAG) operations. Also re-exports
prompt building and KB utilities for backward compatibility after module
reorganization.

Key Features:
    - EmbedderService: Singleton for paraphrase-multilingual-MiniLM-L12-v2
    - Lazy loading: Embedder loaded on first get_embedder() call
    - Memory management: cleanup() releases model to free VRAM/RAM
    - Backward compatibility: Re-exports prompt_utils and kb_utils functions

Classes:
    EmbedderService: Singleton embedder service (do not instantiate directly).

Re-exported Functions (from other modules):
    build_system_prompt: From src.utils.prompt_utils
    get_prompting_strategy: From src.utils.prompt_utils
    get_relevant_texts_from_kb: From src.utils.kb_utils

Notes:
    - Module reorganization: Prompt/KB utilities moved to dedicated modules
    - Embedder model: paraphrase-multilingual-MiniLM-L12-v2 (384 dims)
    - Cache: Models downloaded to CACHE_DIR (backend/data/models_cache/)
    - Singleton pattern: Prevents multiple embedder instances in memory

Examples:
    >>> # Get embedder for KB operations
    >>> from src.utils.inference_utils import EmbedderService
    >>> 
    >>> embedder = EmbedderService.get_embedder()
    >>> embedding = embedder.encode("Sample text")
    >>> print(embedding.shape)  # (384,)
    >>> 
    >>> # Cleanup after batch processing
    >>> EmbedderService.cleanup()
    >>> 
    >>> # Re-exported utilities (backward compatible)
    >>> from src.utils.inference_utils import build_system_prompt
    >>> from src.utils.inference_utils import get_relevant_texts_from_kb
    >>> 
    >>> # Or use new locations directly
    >>> from src.utils.prompt_utils import build_system_prompt
    >>> from src.utils.kb_utils import get_relevant_texts_from_kb

Dependencies:
    - sentence_transformers: SentenceTransformer embedder
    - src.core.config: CACHE_DIR for model storage

Migration Notes:
    **Old imports (still work):**
    - `from src.utils.inference_utils import build_system_prompt`
    - `from src.utils.inference_utils import get_prompting_strategy`
    - `from src.utils.inference_utils import get_relevant_texts_from_kb`

    **New imports (preferred):**
    - `from src.utils.prompt_utils import build_system_prompt`
    - `from src.utils.prompt_utils import get_prompting_strategy`
    - `from src.utils.kb_utils import get_relevant_texts_from_kb`

    Update imports gradually to use new module structure.
"""
import os

from src.core.config import CACHE_DIR
from src.core.logging import logger


class EmbedderService:
    """Singleton service for sentence transformer embedder management.

    Ensures only one embedder instance is loaded in memory across the entire
    application. Provides lazy loading (on first access) and explicit cleanup
    for memory management.

    Usage Pattern:
    1. Call get_embedder() to obtain embedder instance (loads if needed)
    2. Use embedder for encoding text (KB creation, query embedding)
    3. Call cleanup() after batch operations to free memory

    Attributes:
        _instance: Class-level singleton instance (None until first access).

    Methods:
        get_embedder: Get or create embedder instance (classmethod).
        cleanup: Release embedder and free memory (classmethod).

    Examples:
        >>> from src.utils.inference_utils import EmbedderService
        >>> 
        >>> # Get embedder (loads on first call)
        >>> embedder = EmbedderService.get_embedder()
        >>> print(embedder.get_sentence_embedding_dimension())  # 384
        >>> 
        >>> # Encode texts for KB
        >>> texts = ["Sample text 1", "Sample text 2"]
        >>> embeddings = embedder.encode(texts, convert_to_tensor=True)
        >>> print(embeddings.shape)  # (2, 384)
        >>> 
        >>> # Cleanup after batch processing
        >>> EmbedderService.cleanup()
        >>> 
        >>> # Next call will reload embedder
        >>> embedder = EmbedderService.get_embedder()

    Notes:
        - Model: paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions)
        - Cache: Downloads to backend/data/models_cache/
        - Memory: ~470 MB VRAM/RAM when loaded
        - Performance: ~50-100 texts/sec on Apple Silicon M2
        - Thread-safe: Singleton pattern (single instance)
        - DO NOT instantiate: Use get_embedder() classmethod only

    Raises:
        RuntimeError: If __init__ is called directly (use get_embedder instead).

    See Also:
        prepare_for_knowledge_base: Uses embedder for KB creation
        get_relevant_texts_from_kb: Uses embedder for query encoding
    """
    _instance = None
    
    def __init__(self):
        """Prevent direct instantiation of singleton.

        Raises:
            RuntimeError: Always raised. Use get_embedder() classmethod instead.

        Examples:
            >>> # WRONG: Do not instantiate directly
            >>> embedder = EmbedderService()  # Raises RuntimeError
            >>> 
            >>> # CORRECT: Use classmethod
            >>> embedder = EmbedderService.get_embedder()
        """
        raise RuntimeError("Use get_embedder() instead of instantiating")
    
    @classmethod
    def get_embedder(cls):
        """Get or create the singleton embedder instance.

        Lazy-loads the sentence transformer on first call and caches it in
        cls._instance for subsequent calls. Downloads model to CACHE_DIR if
        not already present.

        Returns:
            SentenceTransformer: Loaded paraphrase-multilingual-MiniLM-L12-v2
                model ready for encoding text.

        Examples:
            >>> from src.utils.inference_utils import EmbedderService
            >>> 
            >>> # First call loads model
            >>> embedder = EmbedderService.get_embedder()
            >>> # INFO: Loading the Embedder via EmbedderService
            >>> # INFO: Embedder loaded
            >>> 
            >>> # Subsequent calls return cached instance
            >>> embedder2 = EmbedderService.get_embedder()
            >>> assert embedder is embedder2  # Same object
            >>> 
            >>> # Use embedder
            >>> embedding = embedder.encode("Hello world")
            >>> print(embedding.shape)  # (384,)

        Notes:
            - Thread-safe: Singleton ensures one instance per process
            - Model download: Automatic if not in cache (~470 MB)
            - Cache location: backend/data/models_cache/
            - Logs: INFO level for load start and completion
            - Model: paraphrase-multilingual-MiniLM-L12-v2
            - Dimensions: 384 (compatible with FAISS IndexFlatL2)

        See Also:
            cleanup: Release embedder to free memory
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
        """Release the embedder instance and free memory.

        Deletes the cached embedder instance and sets cls._instance to None.
        This frees VRAM/RAM used by the model (~470 MB). Next call to
        get_embedder() will reload the model.

        Use After:
        - Batch KB creation (multiple files processed)
        - Long-running operations that don't need embedder continuously
        - Memory pressure situations

        Examples:
            >>> from src.utils.inference_utils import EmbedderService
            >>> 
            >>> # Use embedder for batch processing
            >>> embedder = EmbedderService.get_embedder()
            >>> for text in large_text_list:
            ...     embedding = embedder.encode(text)
            ...     # Process embedding...
            >>> 
            >>> # Cleanup after batch
            >>> EmbedderService.cleanup()
            >>> # INFO: Embedder cleaned up
            >>> 
            >>> # Model will reload on next get_embedder()
            >>> embedder = EmbedderService.get_embedder()
            >>> # INFO: Loading the Embedder via EmbedderService

        Notes:
            - Safe to call multiple times (no-op if already None)
            - Does not delete cached model files (only in-memory instance)
            - Logs: INFO level when cleanup performed
            - Memory: Frees ~470 MB VRAM/RAM
            - Performance: Reload takes ~1-2 seconds on fast hardware

        See Also:
            get_embedder: Load or retrieve embedder instance
        """
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
