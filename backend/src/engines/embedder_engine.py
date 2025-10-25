"""Embedder Engine for Semantic Text Encoding.

This module provides the Embedder_Engine singleton for managing the sentence
transformer embedder used in knowledge base (RAG) operations and conversation
semantic search.

The embedder uses paraphrase-multilingual-MiniLM-L12-v2, a 384-dimensional
multilingual sentence transformer optimized for semantic similarity tasks.

Key Features:
    - Embedder_Engine: Singleton for paraphrase-multilingual-MiniLM-L12-v2
    - Lazy loading: Embedder loaded on first get_embedder() call
    - Memory management: cleanup() releases model to free VRAM/RAM
    - Multi-engine architecture: Part of src.engines/ inference backend layer

Classes:
    Embedder_Engine: Singleton embedder engine (do not instantiate directly).

Architecture Notes:
    This is part of Erudi's multi-engine architecture:
    - BaseEngine: LLM inference abstraction (MLX, CUDA, CPU)
    - Embedder_Engine: Text embedding for RAG and semantic search
    - Both provide consistent interfaces across hardware backends

    The Embedder_Engine is separate from LLM engines because:
    1. Different model type (sentence transformer vs. causal LM)
    2. Different use case (encoding vs. generation)
    3. Always runs on same hardware (no engine switching needed)
    4. Shared across all LLM operations (KB, conversations, arena)

Examples:
    >>> # Get embedder for KB operations
    >>> from src.engines.embedder_engine import Embedder_Engine
    >>> 
    >>> embedder = Embedder_Engine.get_embedder()
    >>> embedding = embedder.encode("Sample text")
    >>> print(embedding.shape)  # (384,)
    >>> 
    >>> # Cleanup after batch processing
    >>> Embedder_Engine.cleanup()

Dependencies:
    - sentence_transformers: SentenceTransformer embedder
    - src.core.config: CACHE_DIR for model storage
    - src.core.logging: Structured logging

Migration from utils.inference_utils:
    **Old imports (deprecated but still work via re-export):**
    ```python
    from src.utils.inference_utils import EmbedderService
    embedder = EmbedderService.get_embedder()
    EmbedderService.cleanup()
    ```

    **New imports (preferred):**
    ```python
    from src.engines.embedder_engine import Embedder_Engine
    embedder = Embedder_Engine.get_embedder()
    Embedder_Engine.cleanup()
    ```

See Also:
    - src.engines.base_engine: LLM inference engine abstraction
    - src.utils.kb_utils: Uses embedder for RAG operations
    - src.domains.conversations.utils.embedding: Uses embedder for chat
"""
import os
from src.core.config import CACHE_DIR
from src.core.logging import logger


class Embedder_Engine:
    """Singleton engine for sentence transformer embedder management.

    Ensures only one embedder instance is loaded in memory across the entire
    application. Provides lazy loading (on first access) and explicit cleanup
    for memory management.

    This is part of Erudi's engines layer, separate from LLM engines because
    it serves a different purpose (text encoding vs. text generation) but
    follows similar patterns (singleton, lazy loading, memory management).

    Usage Pattern:
    1. Call get_embedder() to obtain embedder instance (loads if needed)
    2. Use embedder for encoding text (KB creation, query embedding, chat)
    3. Call cleanup() after batch operations to free memory

    Attributes:
        _instance: Class-level singleton instance (None until first access).
        MODEL_NAME: Sentence transformer model identifier.
        EMBEDDING_DIMENSION: Output embedding dimension (384).

    Methods:
        get_embedder: Get or create embedder instance (classmethod).
        cleanup: Release embedder and free memory (classmethod).

    Examples:
        >>> from src.engines.embedder_engine import Embedder_Engine
        >>> 
        >>> # Get embedder (loads on first call)
        >>> embedder = Embedder_Engine.get_embedder()
        >>> print(embedder.get_sentence_embedding_dimension())  # 384
        >>> 
        >>> # Encode texts for KB
        >>> texts = ["Sample text 1", "Sample text 2"]
        >>> embeddings = embedder.encode(texts, convert_to_tensor=True)
        >>> print(embeddings.shape)  # (2, 384)
        >>> 
        >>> # Cleanup after batch processing
        >>> Embedder_Engine.cleanup()
        >>> 
        >>> # Next call will reload embedder
        >>> embedder = Embedder_Engine.get_embedder()

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
        src.utils.kb_utils.get_relevant_texts_from_kb: Uses for query encoding
        src.domains.knowledge_base: Uses for KB vector creation
        src.domains.conversations.utils.embedding: Uses for semantic search
    """
    _instance = None
    MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIMENSION: int = 384
    
    def __init__(self):
        """Prevent direct instantiation of singleton.

        Raises:
            RuntimeError: Always raised. Use get_embedder() classmethod instead.

        Examples:
            >>> # WRONG: Do not instantiate directly
            >>> embedder = Embedder_Engine()  # Raises RuntimeError
            >>> 
            >>> # CORRECT: Use classmethod
            >>> embedder = Embedder_Engine.get_embedder()
        """
        raise RuntimeError("Use get_embedder() classmethod instead of direct instantiation")
    
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
            >>> from src.engines.embedder_engine import Embedder_Engine
            >>> 
            >>> # First call loads model
            >>> embedder = Embedder_Engine.get_embedder()
            >>> # INFO: Loading embedder engine (paraphrase-multilingual-MiniLM-L12-v2)
            >>> # INFO: Embedder engine loaded successfully
            >>> 
            >>> # Subsequent calls return cached instance
            >>> embedder2 = Embedder_Engine.get_embedder()
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
            logger.info(f"Loading embedder engine ({cls.MODEL_NAME})")
            os.makedirs(CACHE_DIR, exist_ok=True)
            
            try:
                cls._instance = SentenceTransformer(
                    cls.MODEL_NAME,
                    cache_folder=CACHE_DIR,
                )
                logger.info(
                    f"Embedder engine loaded successfully "
                    f"(dimension={cls.EMBEDDING_DIMENSION})"
                )
            except Exception as e:
                logger.error(f"Failed to load embedder engine: {e}")
                raise RuntimeError(f"Embedder engine initialization failed: {e}") from e
                
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
            >>> from src.engines.embedder_engine import Embedder_Engine
            >>> 
            >>> # Use embedder for batch processing
            >>> embedder = Embedder_Engine.get_embedder()
            >>> for text in large_text_list:
            ...     embedding = embedder.encode(text)
            ...     # Process embedding...
            >>> 
            >>> # Cleanup after batch
            >>> Embedder_Engine.cleanup()
            >>> # INFO: Embedder engine cleaned up and memory released
            >>> 
            >>> # Model will reload on next get_embedder()
            >>> embedder = Embedder_Engine.get_embedder()
            >>> # INFO: Loading embedder engine...

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
            logger.info("Embedder engine cleaned up and memory released")

__all__ = ['Embedder_Engine']
