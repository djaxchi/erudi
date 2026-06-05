"""Knowledge Base retrieval utilities.

TRANSITIONAL STUB (PostgreSQL/pgvector migration): the FAISS-era retrieval
path died with the VectorStore entity and the on-disk indexes. The hybrid
retrieval (dense HNSW + sparse tsvector, RRF fusion) is rebuilt on
``langchain_postgres.PGVectorStore`` in the vector-store phase of this
migration; until then no KB can hold chunks, so retrieval honestly returns
nothing.
"""
from typing import List

from sqlalchemy.orm import Session

from src.entities.Llm import Llm


def get_relevant_texts_from_kb(
    query: str,
    llm: Llm,
    db: Session,
    kb_top_k: int = 1
) -> List[str]:
    """Retrieve the top-k most relevant KB chunks for a query.

    Args:
        query: User query to search against the KB.
        llm: Specialized Llm whose ``kb_id`` selects the corpus.
        db: Database session.
        kb_top_k: Number of chunks to return.

    Returns:
        Relevant chunk texts, best match first. Currently always empty —
        see module docstring.
    """
    return []
