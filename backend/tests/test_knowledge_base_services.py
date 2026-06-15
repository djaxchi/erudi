"""P7 — KB services: assistant lifecycle + real ingestion pipeline.

Two harnesses on the same embedded cluster:
- Lifecycle/state-machine tests run inside the standard rollback harness
  (``test_db_session``).
- Pipeline tests use a REAL committed session (``real_db_session``): the
  vector store writes through its own connection, so harness-transaction
  rows would be invisible to the chunks' FKs — exactly like the production
  background task, which opens a fresh ``SessionLocal``.
"""

import pytest
import psycopg
from sqlalchemy.orm import sessionmaker

from src.domains.knowledge_base.services import KB_Service
from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.KnowledgeDocument import KnowledgeDocument
from src.entities.Llm import Llm

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Lifecycle / state machine (rollback harness)
# ---------------------------------------------------------------------------

class TestAssistantLifecycle:
    def test_create_kb_assistant_contract(self, test_db_session, mock_llm):
        service = KB_Service()
        llm_id, job_id = service.create_kb_assistant(
            db=test_db_session,
            base_llm_id=mock_llm.id,
            model_name="Assistant Docs",
            description="Assistant spécialisé",
            file_paths=["/tmp/whatever.pdf"],
        )

        specialized = test_db_session.query(Llm).get(llm_id)
        assert specialized.is_attached_to_kb
        assert specialized.local == 1
        assert specialized.kb_id is not None
        assert specialized.name == "Assistant Docs"

        job = service.repo.get_kb_job_by_id(test_db_session, job_id)
        assert job.status == "pending"
        assert job.base_model_id == mock_llm.id
        assert job.new_model_id == llm_id
        assert job.kb_id == specialized.kb_id

    def test_kb_assistant_inherits_supports_tools(self, test_db_session, mock_llm):
        # A KB assistant built from a tool-capable base model must stay
        # tool-capable: otherwise plan_turn routes it to the systematic path and
        # the agentic search_knowledge_base tool is never offered (#84).
        mock_llm.supports_tools = True
        test_db_session.flush()

        service = KB_Service()
        llm_id, _ = service.create_kb_assistant(
            db=test_db_session,
            base_llm_id=mock_llm.id,
            model_name="Tool-capable assistant",
            description="",
            file_paths=["/tmp/whatever.pdf"],
        )

        specialized = test_db_session.query(Llm).get(llm_id)
        assert specialized.supports_tools is True

    def test_create_requires_local_base_llm(self, test_db_session):
        service = KB_Service()
        with pytest.raises(ValueError, match="not found or not local"):
            service.create_kb_assistant(
                db=test_db_session,
                base_llm_id=99999999,
                model_name="X",
                description="",
                file_paths=[],
            )

    def test_update_requires_attached_kb(self, test_db_session, mock_llm):
        service = KB_Service()
        with pytest.raises(ValueError, match="not attached"):
            service.update_existing_kb(
                db=test_db_session, base_llm_id=mock_llm.id, file_paths=[]
            )

    def test_update_creates_job_on_same_llm(self, test_db_session, mock_llm_with_kb):
        llm, kb = mock_llm_with_kb
        service = KB_Service()
        llm_id, job_id = service.update_existing_kb(
            db=test_db_session, base_llm_id=llm.id, file_paths=["/tmp/new.pdf"]
        )
        assert llm_id == llm.id
        job = service.repo.get_kb_job_by_id(test_db_session, job_id)
        assert job.new_model_id == llm.id == job.base_model_id  # update marker
        assert job.kb_id == kb.id

    def test_failed_job_status_triggers_cleanup(self, test_db_session, mock_llm):
        service = KB_Service()
        llm_id, job_id = service.create_kb_assistant(
            db=test_db_session,
            base_llm_id=mock_llm.id,
            model_name="Doomed",
            description="",
            file_paths=[],
        )
        kb_id = test_db_session.query(Llm).get(llm_id).kb_id
        job = service.repo.get_kb_job_by_id(test_db_session, job_id)
        service.repo.update_kb_job_status(test_db_session, job, "failed", "boom")

        status = service.get_kb_job_status(test_db_session, llm_id)

        assert status["status"] == "failed"
        assert status["error_message"] == "boom"
        # Cleanup ran: specialized LLM and its KB are gone, the job remains.
        assert test_db_session.query(Llm).get(llm_id) is None
        assert test_db_session.query(KnowledgeBase).get(kb_id) is None
        assert service.repo.get_kb_job_by_id(test_db_session, job_id) is not None


# ---------------------------------------------------------------------------
# Real ingestion pipeline (committed session + live vector store)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def kb_store(pg_test_cluster, _session_db_engine):
    from src.ingestion import vector_store

    store = vector_store.init_kb_store(pg_test_cluster)
    yield store
    vector_store.close_kb_store()
    with psycopg.connect(pg_test_cluster.psycopg_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS rag.kb_chunks CASCADE")


@pytest.fixture
def real_db_session(_session_db_engine):
    """A genuinely committing session (mirrors the background task's
    SessionLocal). Tracks created KBs and deletes them afterwards —
    cascades sweep documents and chunks."""
    factory = sessionmaker(autocommit=False, autoflush=False, bind=_session_db_engine)
    session = factory()
    created_kb_ids: list[int] = []
    yield session, created_kb_ids
    session.rollback()
    for kb_id in created_kb_ids:
        kb = session.query(KnowledgeBase).get(kb_id)
        if kb:
            session.delete(kb)
    session.commit()
    session.close()


def _make_kb_and_job(session, created_ids):
    service = KB_Service()
    kb = KnowledgeBase()
    session.add(kb)
    session.flush()
    created_ids.append(kb.id)
    job = service.repo.create_kb_job(
        db=session, base_model_id=None, new_model_id=None, kb_id=kb.id
    )
    session.commit()
    return service, kb, job


class TestIngestionPipeline:
    def test_full_pipeline_indexes_searches_and_flags_statuses(
        self, kb_store, real_db_session, tmp_path
    ):
        from src.ingestion.vector_store import search_kb_chunks_scored

        session, created = real_db_session
        service, kb, job = _make_kb_and_job(session, created)

        report = tmp_path / "procédure.md"
        report.write_text(
            "# Remboursement\n\nLa procédure de remboursement prend dix jours ouvrés.",
            encoding="utf-8",
        )
        photo = tmp_path / "photo.jpg"
        photo.write_bytes(b"\xff\xd8\xff\xe0 fake jpeg")

        service.process_and_index_documents(
            db=session, kb_job_id=job.id, file_paths=[str(report), str(photo)]
        )

        session.expire_all()
        assert service.repo.get_kb_job_by_id(session, job.id).status == "completed"

        documents = {
            d.name: d
            for d in session.query(KnowledgeDocument).filter_by(kb_id=kb.id)
        }
        assert documents["procédure.md"].status == "active"
        assert documents["photo.jpg"].status == "pending_vision"
        assert documents["procédure.md"].size_bytes > 0
        assert len(documents["procédure.md"].content_hash_sha256) == 64

        results = search_kb_chunks_scored("délai de remboursement", kb_id=kb.id)
        assert results and "dix jours" in results[0][0].page_content
        assert results[0][0].metadata["document_id"] == documents["procédure.md"].id

    def test_duplicate_file_is_skipped_not_reindexed(
        self, kb_store, real_db_session, tmp_path, pg_test_cluster
    ):
        session, created = real_db_session
        service, kb, job = _make_kb_and_job(session, created)

        doc = tmp_path / "notes.txt"
        doc.write_text("Contenu unique à ne pas dupliquer.", encoding="utf-8")

        service.process_and_index_documents(
            db=session, kb_job_id=job.id, file_paths=[str(doc)]
        )
        # Same content again (update flow re-drops the same file).
        job2 = service.repo.create_kb_job(
            db=session, base_model_id=None, new_model_id=None, kb_id=kb.id
        )
        session.commit()
        service.process_and_index_documents(
            db=session, kb_job_id=job2.id, file_paths=[str(doc)], is_update=True
        )

        session.expire_all()
        assert service.repo.get_kb_job_by_id(session, job2.id).status == "completed"
        count = (
            session.query(KnowledgeDocument).filter_by(kb_id=kb.id).count()
        )
        assert count == 1
        with psycopg.connect(pg_test_cluster.psycopg_url) as conn:
            chunks = conn.execute(
                "SELECT COUNT(*) FROM rag.kb_chunks WHERE kb_id = %s", (kb.id,)
            ).fetchone()[0]
        assert chunks == 1  # not doubled

    def test_unsupported_file_marks_document_failed_but_job_completes(
        self, kb_store, real_db_session, tmp_path
    ):
        session, created = real_db_session
        service, kb, job = _make_kb_and_job(session, created)

        good = tmp_path / "ok.txt"
        good.write_text("Texte parfaitement lisible.", encoding="utf-8")
        bad = tmp_path / "mystère.xyz"
        bad.write_text("format inconnu")

        service.process_and_index_documents(
            db=session, kb_job_id=job.id, file_paths=[str(good), str(bad)]
        )

        session.expire_all()
        assert service.repo.get_kb_job_by_id(session, job.id).status == "completed"
        statuses = {
            d.name: d.status
            for d in session.query(KnowledgeDocument).filter_by(kb_id=kb.id)
        }
        assert statuses == {"ok.txt": "active", "mystère.xyz": "failed"}

    def test_job_fails_when_nothing_could_be_ingested(
        self, kb_store, real_db_session, tmp_path
    ):
        session, created = real_db_session
        service, kb, job = _make_kb_and_job(session, created)

        bad = tmp_path / "broken.xyz"
        bad.write_text("nope")

        with pytest.raises(ValueError, match="No document could be ingested"):
            service.process_and_index_documents(
                db=session, kb_job_id=job.id, file_paths=[str(bad)]
            )

        session.expire_all()
        job_after = service.repo.get_kb_job_by_id(session, job.id)
        assert job_after.status == "failed"
        assert "No document could be ingested" in job_after.error_message
