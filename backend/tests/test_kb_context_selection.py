"""PR3 — adaptive KB context selection (issue #81, problem #2).

Unit tests for the two-stage selection that replaces the flat ``kb_top_k=1``:
1. adaptive cut — keep candidates above the largest dense-similarity
   drop-off (Adaptive-k transposed to our hybrid RRF pool: the cut runs on
   calibrated cosine similarities, never on RRF rank harmonics);
2. token budget — keep whole chunks best-first (RRF order) within the
   model-size budget from ``get_prompting_strategy``.

The selection math is pure (no cluster); ``retrieve_kb_excerpts`` is
exercised with a mocked pool. The real-embeddings behaviour (factoid vs
panorama questions) lives in test_kb_vector_store.py.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from src.core.exceptions import KnowledgeBaseNotFoundException
from src.ingestion.chunking import count_tokens
from src.utils.kb_utils import (
    KbExcerpt,
    _adaptive_threshold,
    _truncate_to_token_budget,
    retrieve_kb_excerpts,
)

pytestmark = pytest.mark.unit


class TestAdaptiveThreshold:
    def test_clear_gap_after_first_keeps_only_the_top(self):
        # One candidate crushes the rest → factoid signature, cut after it.
        sims = [0.92, 0.55, 0.54, 0.53]
        assert _adaptive_threshold(sims) == 0.92

    def test_gap_after_third_keeps_the_cluster(self):
        # Three close candidates then a drop → panorama signature.
        sims = [0.88, 0.86, 0.85, 0.45, 0.44]
        assert _adaptive_threshold(sims) == 0.85

    def test_flat_distribution_has_no_cut_signal(self):
        # No meaningful drop-off → None (the token budget decides alone).
        sims = [0.700, 0.696, 0.693, 0.690]
        assert _adaptive_threshold(sims) is None

    def test_single_candidate_has_no_cut(self):
        assert _adaptive_threshold([0.9]) is None

    def test_empty_pool_has_no_cut(self):
        assert _adaptive_threshold([]) is None

    def test_input_order_does_not_matter(self):
        # The pool arrives in RRF order, not sorted by similarity.
        rrf_order = [0.55, 0.92, 0.54, 0.53]
        assert _adaptive_threshold(rrf_order) == 0.92


class TestTokenBudgetTruncation:
    def test_keeps_whole_chunks_within_budget(self):
        texts = [
            "Le préavis de résiliation est de quatre-vingt-dix jours calendaires.",
            "La redevance mensuelle est facturée à terme à échoir.",
            "Le présent contrat est conclu pour une durée de trente-six mois.",
        ]
        budget = count_tokens(texts[0]) + count_tokens(texts[1])
        assert _truncate_to_token_budget(texts, budget) == texts[:2]

    def test_first_chunk_always_survives_a_tiny_budget(self):
        # Never return zero context because one chunk overflows the budget.
        texts = ["Un chunk nettement plus long que le budget accordé ici."]
        assert _truncate_to_token_budget(texts, 1) == texts

    def test_large_budget_keeps_everything_in_order(self):
        texts = ["alpha", "bravo", "charlie"]
        assert _truncate_to_token_budget(texts, 10_000) == texts

    def test_empty_input(self):
        assert _truncate_to_token_budget([], 500) == []


def _pool(entries):
    return [
        (
            Document(
                page_content=text,
                id=str(i),
                metadata={"source_file": f"doc-{i}.md"},
            ),
            sim,
        )
        for i, (text, sim) in enumerate(entries)
    ]


class TestRetrieveKbExcerpts:
    def test_cut_then_budget_in_rrf_order(self):
        # RRF order ≠ similarity order: the cut filters by similarity but the
        # surviving chunks keep their RRF (best-first) injection order.
        pool = _pool(
            [
                ("chunk pertinent A", 0.88),
                ("chunk pertinent B", 0.86),
                ("chunk hors-sujet", 0.45),
                ("chunk pertinent C", 0.85),
            ]
        )
        llm = SimpleNamespace(kb_id=7)
        with patch("src.utils.kb_utils.search_kb_chunks_scored", return_value=pool):
            excerpts = retrieve_kb_excerpts("question", llm, token_budget=2000)
        assert [e.text for e in excerpts] == [
            "chunk pertinent A", "chunk pertinent B", "chunk pertinent C",
        ]

    def test_excerpts_carry_their_source_file(self):
        pool = _pool([("contenu", 0.9)])
        llm = SimpleNamespace(kb_id=7)
        with patch("src.utils.kb_utils.search_kb_chunks_scored", return_value=pool):
            excerpts = retrieve_kb_excerpts("question", llm, token_budget=2000)
        assert excerpts == [KbExcerpt(source_file="doc-0.md", text="contenu")]

    def test_flat_pool_falls_back_to_budget_only(self):
        pool = _pool([("a", 0.701), ("b", 0.700), ("c", 0.699)])
        llm = SimpleNamespace(kb_id=7)
        with patch("src.utils.kb_utils.search_kb_chunks_scored", return_value=pool):
            excerpts = retrieve_kb_excerpts("question", llm, token_budget=2000)
        assert [e.text for e in excerpts] == ["a", "b", "c"]

    def test_budget_caps_the_survivors(self):
        long_a = "mot " * 120  # well above a 100-token budget on its own
        pool = _pool([(long_a, 0.88), ("suite du contexte", 0.86)])
        llm = SimpleNamespace(kb_id=7)
        with patch("src.utils.kb_utils.search_kb_chunks_scored", return_value=pool):
            excerpts = retrieve_kb_excerpts("question", llm, token_budget=100)
        assert [e.text for e in excerpts] == [long_a]

    def test_empty_pool_returns_empty(self):
        llm = SimpleNamespace(kb_id=7)
        with patch("src.utils.kb_utils.search_kb_chunks_scored", return_value=[]):
            assert retrieve_kb_excerpts("question", llm, token_budget=500) == []

    def test_llm_without_kb_raises(self):
        llm = SimpleNamespace(kb_id=None)
        with pytest.raises(KnowledgeBaseNotFoundException):
            retrieve_kb_excerpts("question", llm, token_budget=500)
