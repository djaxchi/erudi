"""P2b tests — PostgreSQL-native schema: real FKs, server-side cascades,
server-stamped timestamps, and the FAISS-era drops.

Covers the entity reshape of the Postgres migration:
- KnowledgeDocument replaces KnowledgeBase.file_names_list / VectorStore
  (UNIQUE(kb_id, content_hash_sha256), ON DELETE CASCADE).
- KBJob / DownloadJob reference llms / knowledge_base through Integer FKs
  (ON DELETE SET NULL) instead of free-form String columns.
- Message cascade + Conversation llm_id SET NULL are enforced SERVER-side
  (raw SQL DELETE, no ORM cascade involved): a conversation survives its
  model's deletion with a nulled FK (#225).
- created_at / timestamp columns are stamped by the server (func.now()),
  not by client-side Python defaults.
"""

import pytest
from sqlalchemy import Integer, inspect as sa_inspect, text
from sqlalchemy.exc import IntegrityError

from src.entities.Conversation import Conversation
from src.entities.DownloadJob import DownloadJobModel
from src.entities.KBJob import KBJobModel
from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.Llm import Llm
from src.entities.Message import Message


def _make_llm(db, name="Schema Test Model"):
    llm = Llm(name=name, local=1, link="test/model", type="test", param_size=1.0)
    db.add(llm)
    db.flush()
    return llm


def _make_kb(db):
    kb = KnowledgeBase()
    db.add(kb)
    db.flush()
    return kb


def _make_document(db, kb_id, name="doc.pdf", content_hash="a" * 64):
    from src.entities.KnowledgeDocument import KnowledgeDocument

    doc = KnowledgeDocument(
        kb_id=kb_id,
        name=name,
        content_hash_sha256=content_hash,
        size_bytes=1024,
    )
    db.add(doc)
    db.flush()
    return doc


class TestDrops:
    """FAISS-era schema elements are gone."""

    @pytest.mark.integration
    def test_vector_store_table_gone_knowledge_documents_present(self, test_db_engine):
        tables = set(sa_inspect(test_db_engine).get_table_names())
        assert "vector_store" not in tables
        assert "knowledge_documents" in tables

    @pytest.mark.integration
    def test_knowledge_base_faiss_columns_dropped(self, test_db_engine):
        columns = {c["name"] for c in sa_inspect(test_db_engine).get_columns("knowledge_base")}
        assert "index_path" not in columns
        assert "file_names_list" not in columns

    @pytest.mark.integration
    def test_message_is_embedding_cached_dropped(self, test_db_engine):
        columns = {c["name"] for c in sa_inspect(test_db_engine).get_columns("messages")}
        assert "is_embedding_cached" not in columns


class TestKnowledgeDocument:
    @pytest.mark.integration
    def test_create_and_defaults(self, test_db_session):
        kb = _make_kb(test_db_session)
        doc = _make_document(test_db_session, kb.id)
        assert doc.id is not None
        assert doc.status == "active"
        test_db_session.commit()
        assert doc.created_at is not None  # server-stamped

    @pytest.mark.integration
    def test_status_must_be_known(self, test_db_session):
        kb = _make_kb(test_db_session)
        with pytest.raises(ValueError, match="status"):
            _make_document(test_db_session, kb.id, name="x", content_hash="b" * 64).status = (
                "bogus"
            )

    @pytest.mark.integration
    def test_unique_per_kb_and_hash(self, test_db_session):
        kb = _make_kb(test_db_session)
        _make_document(test_db_session, kb.id, name="one.pdf")
        with pytest.raises(IntegrityError):
            _make_document(test_db_session, kb.id, name="two.pdf")  # same hash, same kb
        test_db_session.rollback()

    @pytest.mark.integration
    def test_same_hash_allowed_across_kbs(self, test_db_session):
        kb1 = _make_kb(test_db_session)
        kb2 = _make_kb(test_db_session)
        _make_document(test_db_session, kb1.id)
        _make_document(test_db_session, kb2.id)  # same hash, different kb — fine

    @pytest.mark.integration
    def test_documents_cascade_on_sql_delete_of_kb(self, test_db_session):
        kb = _make_kb(test_db_session)
        _make_document(test_db_session, kb.id, content_hash="c" * 64)
        _make_document(test_db_session, kb.id, content_hash="d" * 64)
        test_db_session.commit()

        # Server-side cascade: bypass the ORM entirely.
        test_db_session.execute(text("DELETE FROM knowledge_base WHERE id = :i"), {"i": kb.id})
        remaining = test_db_session.execute(
            text("SELECT COUNT(*) FROM knowledge_documents WHERE kb_id = :i"), {"i": kb.id}
        ).scalar()
        assert remaining == 0


class TestIntegerForeignKeys:
    """KBJob / DownloadJob String id columns became real Integer FKs."""

    @pytest.mark.integration
    def test_kb_job_columns_are_integers(self, test_db_engine):
        cols = {c["name"]: c["type"] for c in sa_inspect(test_db_engine).get_columns("kb_jobs")}
        for name in ("base_model_id", "new_model_id", "kb_id"):
            assert isinstance(cols[name], Integer), f"{name} should be Integer"
        dl = {
            c["name"]: c["type"]
            for c in sa_inspect(test_db_engine).get_columns("download_jobs")
        }
        assert isinstance(dl["local_model_id"], Integer)

    @pytest.mark.integration
    def test_kb_job_rejects_unknown_llm(self, test_db_session):
        kb = _make_kb(test_db_session)
        job = KBJobModel(base_model_id=99999999, new_model_id=99999999, kb_id=kb.id)
        test_db_session.add(job)
        with pytest.raises(IntegrityError):
            test_db_session.flush()
        test_db_session.rollback()

    @pytest.mark.integration
    def test_kb_job_refs_nulled_when_llm_deleted(self, test_db_session):
        llm = _make_llm(test_db_session)
        kb = _make_kb(test_db_session)
        job = KBJobModel(base_model_id=llm.id, new_model_id=llm.id, kb_id=kb.id)
        test_db_session.add(job)
        test_db_session.commit()

        test_db_session.execute(text("DELETE FROM llms WHERE id = :i"), {"i": llm.id})
        row = test_db_session.execute(
            text("SELECT base_model_id, new_model_id FROM kb_jobs WHERE id = :i"),
            {"i": job.id},
        ).one()
        assert row.base_model_id is None
        assert row.new_model_id is None

    @pytest.mark.integration
    def test_download_job_rejects_unknown_llm(self, test_db_session):
        job = DownloadJobModel(
            remote_model_id="org/model",
            remote_model_link="https://huggingface.co/org/model",
            local_model_id=99999999,
        )
        test_db_session.add(job)
        with pytest.raises(IntegrityError):
            test_db_session.flush()
        test_db_session.rollback()

    @pytest.mark.integration
    def test_download_job_ref_nulled_when_llm_deleted(self, test_db_session):
        llm = _make_llm(test_db_session)
        job = DownloadJobModel(
            remote_model_id="org/model",
            remote_model_link="https://huggingface.co/org/model",
            local_model_id=llm.id,
        )
        test_db_session.add(job)
        test_db_session.commit()

        test_db_session.execute(text("DELETE FROM llms WHERE id = :i"), {"i": llm.id})
        value = test_db_session.execute(
            text("SELECT local_model_id FROM download_jobs WHERE id = :i"), {"i": job.id}
        ).scalar()
        assert value is None


class TestServerSideCascades:
    """ON DELETE behavior enforced by PostgreSQL, not the ORM."""

    @pytest.mark.integration
    def test_messages_cascade_on_sql_delete_of_conversation(self, test_db_session):
        llm = _make_llm(test_db_session)
        conv = Conversation(llm_id=llm.id, name="cascade test")
        test_db_session.add(conv)
        test_db_session.flush()
        test_db_session.add(Message(conversation_id=conv.id, sender="user", content="hello"))
        test_db_session.commit()

        test_db_session.execute(text("DELETE FROM conversations WHERE id = :i"), {"i": conv.id})
        remaining = test_db_session.execute(
            text("SELECT COUNT(*) FROM messages WHERE conversation_id = :i"), {"i": conv.id}
        ).scalar()
        assert remaining == 0

    @pytest.mark.integration
    def test_conversation_survives_sql_delete_of_llm_with_null_fk(self, test_db_session):
        """A conversation is never permanently bound to one model (#225):
        deleting its llm SETs NULL on conversations.llm_id (server-side) instead
        of cascading the conversation away. The row survives, unbound."""
        llm = _make_llm(test_db_session)
        conv = Conversation(llm_id=llm.id, name="survives test")
        test_db_session.add(conv)
        test_db_session.commit()
        llm_id, conv_id = llm.id, conv.id

        test_db_session.execute(text("DELETE FROM llms WHERE id = :i"), {"i": llm_id})
        row = test_db_session.execute(
            text("SELECT llm_id FROM conversations WHERE id = :i"), {"i": conv_id}
        ).one_or_none()
        # Conversation still present, but its FK is nulled.
        assert row is not None
        assert row.llm_id is None


class TestServerDefaults:
    """Timestamps come from the database server, not client-side Python."""

    @pytest.mark.integration
    def test_conversation_created_at_server_stamped(self, test_db_session):
        llm = _make_llm(test_db_session)
        row = test_db_session.execute(
            text(
                "INSERT INTO conversations (llm_id, name) VALUES (:llm_id, :name) "
                "RETURNING created_at, updated_at"
            ),
            {"llm_id": llm.id, "name": "raw insert"},
        ).one()
        assert row.created_at is not None
        assert row.updated_at is not None

    @pytest.mark.integration
    def test_message_timestamp_server_stamped(self, test_db_session):
        llm = _make_llm(test_db_session)
        conv = Conversation(llm_id=llm.id, name="ts test")
        test_db_session.add(conv)
        test_db_session.flush()
        value = test_db_session.execute(
            text(
                "INSERT INTO messages (conversation_id, sender, content, starred) "
                "VALUES (:c, 'user', 'raw', false) RETURNING timestamp"
            ),
            {"c": conv.id},
        ).scalar()
        assert value is not None

    @pytest.mark.integration
    def test_knowledge_base_created_at_server_stamped(self, test_db_session):
        value = test_db_session.execute(
            text("INSERT INTO knowledge_base DEFAULT VALUES RETURNING created_at")
        ).scalar()
        assert value is not None

    @pytest.mark.integration
    def test_messages_relationship_ordered_by_id(self, test_db_session):
        """PG's now() is frozen per transaction: two messages inserted in the
        same transaction share a timestamp. Insertion order must come from the
        monotonically increasing primary key, not the timestamp."""
        llm = _make_llm(test_db_session)
        conv = Conversation(llm_id=llm.id, name="order test")
        test_db_session.add(conv)
        test_db_session.flush()
        first = Message(conversation_id=conv.id, sender="user", content="first")
        second = Message(conversation_id=conv.id, sender="llm", content="second")
        test_db_session.add_all([first, second])
        test_db_session.commit()
        test_db_session.refresh(conv)
        assert [m.content for m in conv.messages] == ["first", "second"]
