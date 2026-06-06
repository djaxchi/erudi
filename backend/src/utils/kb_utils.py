"""Knowledge Base retrieval — hybrid search over ``rag.kb_chunks``.

Thin façade over ``src.ingestion.vector_store.search_kb_chunks`` (dense
HNSW + sparse tsvector, RRF fusion) keeping the historical signature the
conversation/arena layers call.
"""
from typing import List

from src.core.exceptions import KnowledgeBaseNotFoundException
from src.entities.Llm import Llm
from src.ingestion.vector_store import search_kb_chunks


def get_relevant_texts_from_kb(
    query: str,
    llm: Llm,
    kb_top_k: int = 1
) -> List[str]:
    """Retrieve the top-k most relevant KB chunks for a query.

    Args:
        query: User query to search against the KB.
        llm: Specialized Llm whose ``kb_id`` selects the corpus.
        kb_top_k: Number of chunks to return.

    Returns:
        Relevant chunk texts (best match first); empty when the KB holds
        no indexed chunks yet.

    Raises:
        KnowledgeBaseNotFoundException: If the LLM has no KB attached.
    """
    if not llm.kb_id:
        raise KnowledgeBaseNotFoundException(llm.kb_id)

    documents = search_kb_chunks(query, kb_id=llm.kb_id, k=kb_top_k)
    return [document.page_content for document in documents]
