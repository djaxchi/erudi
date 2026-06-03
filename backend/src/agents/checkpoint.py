"""LangGraph SQLite checkpointer wiring.

The agent's conversation state (message history + summaries) is persisted by a
LangGraph ``AsyncSqliteSaver`` in a SEPARATE SQLite file (``erudi-checkpoints.db``)
from the business DB (``erudi.db``). This keeps the LangGraph-managed schema
(``checkpoints``/``writes``) isolated from the SQLAlchemy/alembic business schema
and lets the checkpoint store be dropped/rebuilt without touching business data.

The saver is held open for the whole application lifetime (FastAPI ``lifespan``)
and exposed on ``app.state.checkpointer``; endpoints reach it via
``get_checkpointer``. In tests the ``client`` fixture injects an ``InMemorySaver``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.core.logging import logger

# Busy timeout (ms) so a checkpoint write does not raise "database is locked"
# when another connection (a delete, a summarization rewrite) touches the file.
_BUSY_TIMEOUT_MS = 30_000


@asynccontextmanager
async def open_checkpointer(db_path: Path | str) -> AsyncIterator[AsyncSqliteSaver]:
    """Open an ``AsyncSqliteSaver`` held for the whole app lifetime.

    ``AsyncSqliteSaver.from_conn_string`` is itself an async context manager that
    CLOSES its aiosqlite connection on ``__aexit__``, so we wrap it and keep it
    entered across the lifespan (the lifespan enters this CM manually and exits it
    on shutdown). ``setup()`` creates the ``checkpoints``/``writes`` tables
    (idempotent) and enables WAL; we additionally set a busy timeout on the same
    connection.

    Yields a ready-to-use saver.
    """
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        await saver.setup()  # creates tables (idempotent) + PRAGMA journal_mode=WAL
        await saver.conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        logger.info(f"Conversation checkpointer ready at {db_path}")
        yield saver


def get_checkpointer(request: Request) -> BaseCheckpointSaver:
    """FastAPI dependency returning the app-wide checkpointer from ``app.state``.

    Set during ``lifespan`` startup (``AsyncSqliteSaver``). In tests the ``client``
    fixture injects an ``InMemorySaver`` onto ``app.state.checkpointer``.
    """
    return request.app.state.checkpointer
