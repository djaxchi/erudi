"""P3 — checkpointer wiring (PostgreSQL).

Covers the wiring guarantees on the embedded cluster:
  - ``open_checkpointer`` yields a ready ``AsyncPostgresSaver`` (tables created
    in the same database as the business schema, thread isolation,
    ``adelete_thread`` purges a single thread — the B3 mechanism),
  - checkpoint state survives closing and reopening the saver (app restart),
  - ``get_checkpointer`` exposes ``app.state.checkpointer`` to endpoints.
"""

import os
import uuid
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.base import empty_checkpoint

pytestmark = pytest.mark.integration


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}


def test_strict_msgpack_env_default_is_set():
    from src.core import config  # noqa: F401  (import sets the env default)

    assert os.environ.get("LANGGRAPH_STRICT_MSGPACK") == "true"


async def test_open_checkpointer_creates_tables_and_isolates_threads(pg_test_cluster):
    from src.agents.checkpoint import open_checkpointer

    thread_a, thread_b = f"A-{uuid.uuid4()}", f"B-{uuid.uuid4()}"
    async with open_checkpointer(pg_test_cluster.psycopg_url) as saver:
        await saver.aput(_cfg(thread_a), empty_checkpoint(), {"source": "input", "step": 0}, {})
        await saver.aput(_cfg(thread_b), empty_checkpoint(), {"source": "input", "step": 0}, {})
        assert await saver.aget_tuple(_cfg(thread_a)) is not None
        assert await saver.aget_tuple(_cfg(thread_b)) is not None

        # B3: deleting one conversation's thread leaves the other intact.
        await saver.adelete_thread(thread_a)
        assert await saver.aget_tuple(_cfg(thread_a)) is None
        assert await saver.aget_tuple(_cfg(thread_b)) is not None

        await saver.adelete_thread(thread_b)


async def test_checkpoint_state_survives_reopen(pg_test_cluster):
    # State written through one saver is visible after closing it and opening
    # a new one on the same cluster — proving conversations persist across an
    # app restart (production holds the saver open for the whole lifespan,
    # but a relaunch must restore prior threads).
    from src.agents.checkpoint import open_checkpointer

    thread = f"persist-{uuid.uuid4()}"
    async with open_checkpointer(pg_test_cluster.psycopg_url) as saver:
        await saver.aput(_cfg(thread), empty_checkpoint(), {"source": "input", "step": 0}, {})
        assert await saver.aget_tuple(_cfg(thread)) is not None

    # Reopen (simulates a process restart).
    async with open_checkpointer(pg_test_cluster.psycopg_url) as saver2:
        assert await saver2.aget_tuple(_cfg(thread)) is not None
        await saver2.adelete_thread(thread)


async def test_checkpointer_tables_live_in_business_database(pg_test_cluster):
    # One database (`erudi`), business + checkpointer schemas side by side:
    # the LangGraph-managed tables must land in the SAME database the
    # SQLAlchemy engine uses, so a single cluster backup captures everything.
    import psycopg

    from src.agents.checkpoint import open_checkpointer

    async with open_checkpointer(pg_test_cluster.psycopg_url):
        pass

    with psycopg.connect(pg_test_cluster.psycopg_url) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
        }
    assert "checkpoints" in tables
    assert "checkpoint_writes" in tables


def test_get_checkpointer_reads_app_state():
    from src.agents.checkpoint import get_checkpointer

    sentinel = object()
    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=sentinel))
    )
    assert get_checkpointer(fake_request) is sentinel


def test_checkpoint_db_path_is_gone():
    # The SQLite-era CHECKPOINT_DB_PATH must not survive the migration.
    from src.core import config

    assert not hasattr(config, "CHECKPOINT_DB_PATH")
