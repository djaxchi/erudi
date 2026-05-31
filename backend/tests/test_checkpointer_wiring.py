"""P1 — checkpointer wiring.

Covers the three wiring guarantees:
  - the checkpointer lives in a SEPARATE SQLite file inside DATA_ROOT,
  - ``open_checkpointer`` yields a ready saver (tables created, thread isolation,
    ``adelete_thread`` purges a single thread — the B3 mechanism),
  - ``get_checkpointer`` exposes ``app.state.checkpointer`` to endpoints.
"""

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.base import empty_checkpoint

pytestmark = pytest.mark.unit


def test_checkpoint_db_is_separate_sibling_of_business_db():
    from src.core import config

    assert config.CHECKPOINT_DB_PATH.parent == config.DATA_ROOT
    assert config.CHECKPOINT_DB_PATH.name == "erudi-checkpoints.db"
    assert config.CHECKPOINT_DB_PATH != (config.DATA_ROOT / "erudi.db")


def test_strict_msgpack_env_default_is_set():
    from src.core import config  # noqa: F401  (import sets the env default)

    assert os.environ.get("LANGGRAPH_STRICT_MSGPACK") == "true"


async def test_open_checkpointer_creates_tables_and_isolates_threads():
    from src.agents.checkpoint import open_checkpointer

    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "cp.db"
        async with open_checkpointer(db) as saver:
            cur = await saver.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [r[0] for r in await cur.fetchall()]
            assert "checkpoints" in tables and "writes" in tables

            # WAL + busy_timeout configured on the held-open connection.
            cur = await saver.conn.execute("PRAGMA busy_timeout")
            assert (await cur.fetchone())[0] == 30000

            cfg_a = {"configurable": {"thread_id": "A", "checkpoint_ns": ""}}
            cfg_b = {"configurable": {"thread_id": "B", "checkpoint_ns": ""}}
            await saver.aput(cfg_a, empty_checkpoint(), {"source": "input", "step": 0}, {})
            await saver.aput(cfg_b, empty_checkpoint(), {"source": "input", "step": 0}, {})
            assert await saver.aget_tuple(cfg_a) is not None
            assert await saver.aget_tuple(cfg_b) is not None

            # B3: deleting one conversation's thread leaves the other intact.
            await saver.adelete_thread("A")
            assert await saver.aget_tuple(cfg_a) is None
            assert await saver.aget_tuple(cfg_b) is not None


def test_get_checkpointer_reads_app_state():
    from src.agents.checkpoint import get_checkpointer

    sentinel = object()
    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=sentinel))
    )
    assert get_checkpointer(fake_request) is sentinel
