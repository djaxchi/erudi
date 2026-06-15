"""Knowledge Base retrieval — adaptive context selection over hybrid search.

Two-stage SOTA selection (issue #81), replacing the flat ``kb_top_k=1`` that
starved panorama and cross-document questions by construction:

1. ``search_kb_chunks_scored`` fetches a wide hybrid candidate pool (dense
   HNSW + sparse tsvector, RRF order) with each candidate's dense cosine
   similarity.
2. Adaptive cut (Adaptive-k transposed to our stack): keep the candidates
   above the largest similarity drop-off, so factoid questions inject a
   narrow context while panorama questions keep their whole cluster. The
   cut runs on calibrated dense cosines — NEVER on RRF scores, which are
   rank harmonics with no semantic scale.
3. Token budget: keep whole chunks best-first (RRF order — primacy beats
   burying, per the lost-in-the-middle literature) within the model-size
   budget from ``get_prompting_strategy``.

Excerpts carry their ``source_file`` so the KB prompt can attribute each
one ("according to <document>" grounding) — see ``build_kb_system_prompt``.
"""
from dataclasses import dataclass
from typing import List, Optional, Sequence

from src.core.exceptions import KnowledgeBaseNotFoundException
from src.ingestion.chunking import count_tokens
from src.ingestion.vector_store import search_kb_chunks_scored


@dataclass(frozen=True)
class KbExcerpt:
    """One selected KB chunk, ready for prompt injection."""

    source_file: str
    text: str

# Below this, a similarity drop-off is noise, not a cut signal: e5 cosines
# live in a compressed range, so a flat pool falls through to budget-only.
MIN_SIMILARITY_GAP = 0.01


def _adaptive_threshold(similarities: Sequence[float]) -> Optional[float]:
    """Similarity at the largest drop-off — candidates below it get cut.

    Returns ``None`` when there is no usable signal (fewer than two
    candidates, or a flat distribution): the caller keeps everything and
    lets the token budget decide alone.
    """
    if len(similarities) < 2:
        return None
    ordered = sorted(similarities, reverse=True)
    gaps = [ordered[i] - ordered[i + 1] for i in range(len(ordered) - 1)]
    widest = max(gaps)
    if widest < MIN_SIMILARITY_GAP:
        return None
    return ordered[gaps.index(widest)]


def _truncate_to_token_budget(texts: List[str], token_budget: int) -> List[str]:
    """Keep whole chunks, best-first, within ``token_budget`` e5 tokens.

    The first chunk always survives — one oversized chunk must yield a big
    context, never an empty one.
    """
    kept: List[str] = []
    spent = 0
    for text in texts:
        cost = count_tokens(text)
        if kept and spent + cost > token_budget:
            break
        kept.append(text)
        spent += cost
    return kept


def retrieve_kb_excerpts(
    query: str,
    kb_id: Optional[int],
    token_budget: int,
) -> List[KbExcerpt]:
    """Select the KB context for a query: pool → adaptive cut → token budget.

    Args:
        query: User query to search against the KB.
        kb_id: KnowledgeBase id selecting the corpus (the model's ``kb_id``;
            the agentic tool passes it from its runtime context).
        token_budget: Max context size in e5 tokens (from the model-size
            strategy, ``get_prompting_strategy``).

    Returns:
        Source-attributed excerpts in RRF order (best match first); empty
        when the KB holds no indexed chunks yet.

    Raises:
        KnowledgeBaseNotFoundException: If no ``kb_id`` is provided.
    """
    if not kb_id:
        raise KnowledgeBaseNotFoundException(kb_id)

    pool = search_kb_chunks_scored(query, kb_id=kb_id)
    if not pool:
        return []

    threshold = _adaptive_threshold([sim for _, sim in pool])
    if threshold is not None:
        pool = [(doc, sim) for doc, sim in pool if sim >= threshold]

    excerpts = [
        KbExcerpt(
            source_file=doc.metadata.get("source_file", ""),
            text=doc.page_content,
        )
        for doc, _ in pool
    ]
    # The budget keeps a prefix (best-first order), so indices line up.
    kept = _truncate_to_token_budget([e.text for e in excerpts], token_budget)
    return excerpts[: len(kept)]
