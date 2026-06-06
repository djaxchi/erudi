"""P6 — hybrid KB vector store on rag.kb_chunks (PGVectorStore).

Real embedded cluster, real e5 embeddings, no mocks:
- schema/table/HNSW/FK wiring (cross-schema ON DELETE CASCADE [M3]),
- idempotent boot-time init,
- kb_id-filtered hybrid search (dense HNSW + sparse tsvector, RRF k=60),
- anti-regression for the langchain-postgres shared-config bug (the first
  query's fts_query froze onto the store config and contaminated every
  later sparse search — our layer passes a FRESH config per search),
- golden queries FR/EN — the 384d gate: if this fails, escalate the
  embedder to e5-base BEFORE merge.
"""

import pytest
import psycopg

from src.ingestion.chunking import Chunk

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def kb_store(pg_test_cluster, _session_db_engine):
    """Boot-shaped store init: business tables first (FKs), then the store."""
    from src.ingestion import vector_store

    store = vector_store.init_kb_store(pg_test_cluster)
    yield store
    vector_store.close_kb_store()
    # Drop the rag table here (module teardown) so the session-scoped
    # Base.metadata.drop_all isn't blocked by the cross-schema FKs.
    with psycopg.connect(pg_test_cluster.psycopg_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS rag.kb_chunks CASCADE")


@pytest.fixture
def kb_rows(pg_test_cluster):
    """Two committed KBs + one document each (the store reads through its
    own connection, so harness-transaction rows would be invisible)."""
    created: list[int] = []
    with psycopg.connect(pg_test_cluster.psycopg_url, autocommit=True) as conn:
        ids = {}
        for label in ("a", "b"):
            kb_id = conn.execute(
                "INSERT INTO knowledge_base DEFAULT VALUES RETURNING id"
            ).fetchone()[0]
            doc_id = conn.execute(
                "INSERT INTO knowledge_documents"
                " (kb_id, name, content_hash_sha256, size_bytes, status)"
                " VALUES (%s, %s, %s, 1024, 'active') RETURNING id",
                (kb_id, f"doc_{label}.pdf", label * 64),
            ).fetchone()[0]
            ids[label] = (kb_id, doc_id)
            created.append(kb_id)
    yield ids
    with psycopg.connect(pg_test_cluster.psycopg_url, autocommit=True) as conn:
        for kb_id in created:
            conn.execute("DELETE FROM knowledge_base WHERE id = %s", (kb_id,))


def _chunks(texts: list[str]) -> list[Chunk]:
    return [
        Chunk(chunk_index=i, text=t, token_count=len(t.split()), page_number=None)
        for i, t in enumerate(texts)
    ]


def _add(kb_id: int, doc_id: int, texts: list[str], source_file: str = "doc.pdf"):
    from src.ingestion.vector_store import add_kb_chunks

    return add_kb_chunks(
        kb_id=kb_id,
        document_id=doc_id,
        source_file=source_file,
        chunks=_chunks(texts),
    )


class TestWiring:
    def test_table_columns_fks_and_hnsw_index(self, kb_store, pg_test_cluster):
        with psycopg.connect(pg_test_cluster.psycopg_url) as conn:
            columns = {
                row[0]
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = 'rag' AND table_name = 'kb_chunks'"
                )
            }
            assert {
                "langchain_id",
                "content",
                "embedding",
                "content_tsv",
                "kb_id",
                "document_id",
                "source_file",
                "page",
                "chunk_index",
            } <= columns

            fks = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT conname, confdeltype FROM pg_constraint"
                    " WHERE conrelid = 'rag.kb_chunks'::regclass AND contype = 'f'"
                )
            }
            assert fks.get("fk_kb_chunks_kb_id") == "c"  # ON DELETE CASCADE
            assert fks.get("fk_kb_chunks_document_id") == "c"

            indexes = {
                row[0]
                for row in conn.execute(
                    "SELECT indexname FROM pg_indexes"
                    " WHERE schemaname = 'rag' AND tablename = 'kb_chunks'"
                )
            }
            assert "idx_kb_chunks_embedding_hnsw" in indexes

    def test_init_is_idempotent_and_preserves_data(
        self, kb_store, kb_rows, pg_test_cluster
    ):
        from src.ingestion import vector_store

        kb_id, doc_id = kb_rows["a"]
        _add(kb_id, doc_id, ["Donnée qui doit survivre à un second boot."])

        vector_store.init_kb_store(pg_test_cluster)  # second boot

        with psycopg.connect(pg_test_cluster.psycopg_url) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM rag.kb_chunks WHERE kb_id = %s", (kb_id,)
            ).fetchone()[0]
        assert count == 1


class TestSearch:
    def test_search_is_filtered_by_kb_and_carries_metadata(self, kb_store, kb_rows):
        from src.ingestion.vector_store import search_kb_chunks

        kb_a, doc_a = kb_rows["a"]
        kb_b, doc_b = kb_rows["b"]
        _add(kb_a, doc_a, ["Paris est la capitale de la France."], "geo.pdf")
        _add(kb_b, doc_b, ["Paris est la capitale de la France."], "copie.pdf")

        results = search_kb_chunks("capitale de la France", kb_id=kb_a, k=5)
        assert results
        assert all(doc.metadata["kb_id"] == kb_a for doc in results)
        top = results[0].metadata
        assert top["document_id"] == doc_a
        assert top["source_file"] == "geo.pdf"
        assert top["chunk_index"] == 0

    def test_successive_searches_keep_correct_ranking(self, kb_store, kb_rows):
        """Anti-regression: langchain-postgres freezes the first query's
        fts_query onto the SHARED store config, poisoning every later
        sparse search. Our layer must pass a fresh config per search."""
        from src.ingestion.vector_store import search_kb_chunks

        kb_id, doc_id = kb_rows["a"]
        _add(
            kb_id,
            doc_id,
            [
                "Paris est la capitale de la France.",
                "Le contrat REF-88412 expire en mars.",
                "Le chat dort paisiblement sur le canapé.",
            ],
        )

        first = search_kb_chunks("REF-88412", kb_id=kb_id, k=1)
        assert "REF-88412" in first[0].page_content

        second = search_kb_chunks("capitale de la France", kb_id=kb_id, k=1)
        assert "capitale" in second[0].page_content

        third = search_kb_chunks("Qui dort sur le canapé ?", kb_id=kb_id, k=1)
        assert "chat" in third[0].page_content

    def test_stored_content_is_clean_for_generation(
        self, kb_store, kb_rows, pg_test_cluster
    ):
        """The [document_name:…] prefix is EMBEDDING-time text only: stored
        content must be the clean chunk (it goes verbatim into the LLM's
        prompt — tiny models loop on the bracketed prefix), and the sparse
        tsv must still be populated by the embeddings-provided insert path."""
        kb_id, doc_id = kb_rows["a"]
        _add(kb_id, doc_id, ["Contenu du chunk."], "rapport.pdf")
        with psycopg.connect(pg_test_cluster.psycopg_url) as conn:
            content, tsv_filled = conn.execute(
                "SELECT content, content_tsv IS NOT NULL FROM rag.kb_chunks"
                " WHERE kb_id = %s",
                (kb_id,),
            ).fetchone()
        assert content == "Contenu du chunk."
        assert "[document_name:" not in content
        assert tsv_filled

    def test_document_name_contributes_to_the_embedding(
        self, kb_store, kb_rows, pg_test_cluster
    ):
        """Same chunk text under two different file names → different vectors:
        proof the document name is part of the embedded text (retrieval
        benefit kept) even though the stored content is clean."""
        kb_id, doc_id = kb_rows["a"]
        _add(kb_id, doc_id, ["Texte identique."], "alpha.pdf")
        _add(kb_id, doc_id, ["Texte identique."], "beta.pdf")
        with psycopg.connect(pg_test_cluster.psycopg_url) as conn:
            distinct = conn.execute(
                "SELECT COUNT(DISTINCT embedding::text) FROM rag.kb_chunks"
                " WHERE kb_id = %s",
                (kb_id,),
            ).fetchone()[0]
        assert distinct == 2


class TestCascade:
    def test_delete_kb_cascades_cross_schema_to_chunks(
        self, kb_store, kb_rows, pg_test_cluster
    ):
        kb_id, doc_id = kb_rows["a"]
        _add(kb_id, doc_id, ["Chunk voué à disparaître avec sa KB."])

        with psycopg.connect(pg_test_cluster.psycopg_url, autocommit=True) as conn:
            conn.execute("DELETE FROM knowledge_base WHERE id = %s", (kb_id,))
            remaining = conn.execute(
                "SELECT COUNT(*) FROM rag.kb_chunks WHERE kb_id = %s", (kb_id,)
            ).fetchone()[0]
        assert remaining == 0


class TestKbUtils:
    def test_get_relevant_texts_returns_chunk_contents(self, kb_store, kb_rows):
        from types import SimpleNamespace

        from src.utils.kb_utils import get_relevant_texts_from_kb

        kb_id, doc_id = kb_rows["a"]
        _add(kb_id, doc_id, ["La procédure de remboursement prend dix jours."])

        llm = SimpleNamespace(kb_id=kb_id)
        texts = get_relevant_texts_from_kb("délai de remboursement", llm, kb_top_k=1)
        assert len(texts) == 1
        assert "remboursement" in texts[0]


GOLDEN_CORPUS = [
    "La tour Eiffel mesure 330 mètres de haut et se trouve à Paris.",
    "Le télétravail est autorisé trois jours par semaine dans l'entreprise.",
    "La facture FAC-2024-0917 a été réglée le 15 mars.",
    "Pour réinitialiser votre mot de passe, cliquez sur « Mot de passe oublié ».",
    "Le chiffre d'affaires du troisième trimestre a progressé de 12 %.",
    "The quarterly security audit found no critical vulnerabilities.",
    "Employees must badge in before entering the server room.",
    "The new API gateway reduces median latency by 40 milliseconds.",
    "Annual leave requests must be submitted two weeks in advance.",
    "The Berlin office relocates to Alexanderplatz in January.",
]

GOLDEN_QUERIES = [
    ("Quelle est la hauteur de la tour Eiffel ?", 0),
    ("Combien de jours de télétravail par semaine ?", 1),
    ("FAC-2024-0917", 2),  # exact id — sparse branch must nail it
    ("Comment changer mon mot de passe ?", 3),  # paraphrase
    ("évolution du CA au troisième trimestre", 4),  # abbreviation paraphrase
    ("Were any critical vulnerabilities found in the audit?", 5),
    ("How early should I submit my vacation request?", 8),  # EN paraphrase
    ("Where is the Berlin office moving to?", 9),
]


class TestGoldenQueries:
    """The 384d gate: e5-small must resolve these on a realistic mixed
    corpus. Failure → escalate to e5-base (768d) BEFORE merge."""

    def test_golden_queries_fr_en(self, kb_store, kb_rows):
        from src.ingestion.vector_store import search_kb_chunks

        kb_id, doc_id = kb_rows["a"]
        _add(kb_id, doc_id, GOLDEN_CORPUS, "golden.md")

        top1_hits = 0
        misses: list[str] = []
        for query, expected_idx in GOLDEN_QUERIES:
            expected = GOLDEN_CORPUS[expected_idx]
            results = search_kb_chunks(query, kb_id=kb_id, k=2)
            contents = [r.page_content for r in results]
            if contents and expected in contents[0]:
                top1_hits += 1
            elif not any(expected in c for c in contents):
                misses.append(f"{query!r} → got {contents[:1]}")

        # Hard gate: every query lands in top-2; soft gate: ≥ 6/8 are top-1.
        assert not misses, f"golden queries missing from top-2: {misses}"
        assert top1_hits >= 6, f"only {top1_hits}/8 golden queries hit top-1"
