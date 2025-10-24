"""
Knowledge Base utilities shared across domains.
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
from src.utils.inference_utils import EmbedderService
from src.core.logging import logger


def get_relevant_texts_from_kb(
    query: str,
    llm: Llm,
    db: Session,
    kb_top_k: int = 1
) -> List[str]:
    """
    Retrieve relevant text chunks from a knowledge base using semantic search.
    
    Args:
        query: The search query.
        llm: The language model with attached knowledge base.
        db: Database session.
        kb_top_k: Number of most relevant chunks to retrieve.
    
    Returns:
        List of relevant text chunks.
    
    Raises:
        Exception: If KB resources are missing or search fails.
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
    embedder = EmbedderService.get_embedder()
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

    EmbedderService.cleanup()
    return relevant_texts
