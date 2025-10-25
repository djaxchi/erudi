"""Knowledge Base RAG Utilities for Semantic Search.

This module provides utilities for retrieving relevant text chunks from FAISS
knowledge bases using semantic similarity search. Integrates with the multi-tier
memory system for context injection in LLM conversations.

Key Features:
    - FAISS vector similarity search
    - Query embedding and chunking
    - Top-k retrieval from VectorStore
    - Error handling for missing KB resources
    - Embedder_Engine cleanup after retrieval

Functions:
    get_relevant_texts_from_kb: Semantic search for relevant KB chunks.

Dependencies:
    - faiss: Vector similarity search engine
    - numpy: Array operations for FAISS
    - sentence_transformers: Embedder via Embedder_Engine
    - sqlalchemy: Database session for KB/VectorStore queries

Examples:
    >>> # Retrieve relevant chunks for a query
    >>> from src.utils.kb_utils import get_relevant_texts_from_kb
    >>> from src.database.core import get_db
    >>> from sqlalchemy.orm import Session
    >>> 
    >>> db: Session = next(get_db())
    >>> llm = db.query(Llm).filter(Llm.id == 35).first()  # KB-attached model
    >>> 
    >>> relevant_texts = get_relevant_texts_from_kb(
    ...     query="How to implement async endpoints in FastAPI?",
    ...     llm=llm,
    ...     db=db,
    ...     kb_top_k=3
    ... )
    >>> for text in relevant_texts:
    ...     print(text[:100])  # First 100 chars of each chunk

Notes:
    - Requires llm.is_attached_to_kb=True and valid kb_id
    - FAISS index must exist at kb.index_path
    - VectorStore must exist for KB (vectors_data JSON)
    - Query is chunked via chunk_by_tokens for embedding
    - Returns empty list if query produces no valid chunks
    - Embedder_Engine.cleanup() called after retrieval (memory management)
"""
import os
import numpy
import faiss
from typing import List

from sqlalchemy.orm import Session

from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.Llm import Llm
from src.entities.VectorStore import VectorStore
from src.utils.file_processor import chunk_by_tokens
from src.engines.embedder_engine import Embedder_Engine
from src.core.logging import logger


def get_relevant_texts_from_kb(
    query: str,
    llm: Llm,
    db: Session,
    kb_top_k: int = 1
) -> List[str]:
    """Retrieve relevant text chunks from knowledge base using semantic search.

    Performs FAISS vector similarity search to find the most relevant chunks
    from the LLM's attached knowledge base. Query is embedded using the same
    embedder model that created the KB index (paraphrase-multilingual-MiniLM).

    Process Flow:
    1. **Validate**: Check KB exists, index file accessible, VectorStore present
    2. **Load Index**: Read FAISS index from disk
    3. **Chunk Query**: Split query into token-limited chunks via chunk_by_tokens
    4. **Embed**: Encode each query chunk with Embedder_Engine
    5. **Search**: FAISS similarity search (top-k per chunk)
    6. **Collect**: Gather text from VectorStore.vectors_data by FAISS IDs
    7. **Cleanup**: Release embedder memory

    Args:
        query: User query or message content to search for. Can be any length
            (will be chunked if >384 tokens).
        llm: Llm entity with is_attached_to_kb=True and valid kb_id. Must
            have an associated KnowledgeBase and VectorStore.
        db: SQLAlchemy database session for querying KB and VectorStore.
        kb_top_k: Number of most similar chunks to retrieve per query chunk
            (default: 1). Higher values provide more context but may introduce
            noise. Typical range: 1-5.

    Returns:
        List of relevant text chunk strings from KB, ordered by similarity
        (most relevant first). May contain duplicates if multiple query chunks
        match the same KB chunk. Empty list if query produces no valid chunks
        or search fails gracefully.

    Raises:
        Exception: If KB index not found, FAISS read fails, or VectorStore
            missing. These are critical errors indicating KB corruption or
            incomplete setup.

    Examples:
        >>> from src.utils.kb_utils import get_relevant_texts_from_kb
        >>> from src.database.core import get_db
        >>> 
        >>> db = next(get_db())
        >>> llm = db.query(Llm).filter(Llm.id == 35).first()
        >>> 
        >>> # Single top result
        >>> texts = get_relevant_texts_from_kb(
        ...     query="What is FastAPI?",
        ...     llm=llm,
        ...     db=db,
        ...     kb_top_k=1
        ... )
        >>> print(texts[0][:200])  # Most relevant chunk
        >>> 
        >>> # Multiple results for broader context
        >>> texts = get_relevant_texts_from_kb(
        ...     query="How to handle database connections in async routes?",
        ...     llm=llm,
        ...     db=db,
        ...     kb_top_k=3
        ... )
        >>> print(f"Found {len(texts)} relevant chunks")

    Notes:
        - Embedder: Uses paraphrase-multilingual-MiniLM-L12-v2 (384 dims)
        - FAISS: L2 distance metric (lower is more similar)
        - Query chunking: Necessary for long queries (>384 tokens)
        - Memory: Embedder_Engine.cleanup() releases model after use
        - Performance: ~10-50ms per query depending on index size and top-k
        - Error handling: Logs and skips chunks that fail to embed
        - Invalid indices: Skips FAISS indices <0 (no match found)

    See Also:
        chunk_by_tokens: Query chunking implementation
        Embedder_Engine: Singleton embedder with memory management
        prepare_for_knowledge_base: KB creation from PDFs/TXTs
    """
    # Validate knowledge base exists and is accessible
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == llm.kb_id).first()
    if not kb or not os.path.exists(kb.index_path):
        raise Exception(f"Knowledge Base index not found for LLM {llm.id}")

    # Load FAISS index
    try:
        faiss_index = faiss.read_index(kb.index_path)
        if not faiss_index:
            raise Exception(f"FAISS index not found for Knowledge Base {kb.id}")
    except Exception as e:
        raise Exception(f"Failed to read FAISS index for Knowledge Base {kb.id}") from e

    # Get vector store
    vector_store = db.query(VectorStore).filter(VectorStore.kb_id == kb.id).first()
    if not vector_store:
        raise Exception(f"VectorStore not found for Knowledge Base {kb.id}")

    # Process query
    embedder = Embedder_Engine.get_embedder()
    chunks = chunk_by_tokens(text=query)
    if not chunks:
        raise Exception("No valid text chunks found in the query.")

    relevant_texts = []
    for chunk in chunks:
        if not chunk.strip():
            continue

        # Encode query chunk
        try:
            logger.info(f"Encoding query chunk: {chunk[:50]}...")
            query_emb = embedder.encode(chunk, convert_to_tensor=True)
            if query_emb is None or query_emb.numel() == 0:
                raise Exception("Error embedding chunk.")
        except Exception as e:
            logger.error(f"Error embedding chunk: {e}")
            continue

        # Search similar vectors
        try:
            q = numpy.ascontiguousarray(
                query_emb.detach().cpu().numpy().astype("float32")
            ).reshape(1, -1)
            _, I = faiss_index.search(q, k=kb_top_k)
            
            # Collect matching texts
            for idx in I[0]:
                if idx >= 0:  # Skip invalid indices
                    faiss_id_str = str(idx)
                    if faiss_id_str in vector_store.vectors_data:
                        relevant_texts.append(vector_store.vectors_data[faiss_id_str])
        except Exception as e:
            raise Exception(f"Error searching FAISS index: {str(e)}") from e

    Embedder_Engine.cleanup()
    return relevant_texts
