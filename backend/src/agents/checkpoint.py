"""LangGraph PostgreSQL checkpointer wiring.

The agent's conversation state (message history + summaries) is persisted by a
LangGraph ``AsyncPostgresSaver`` in the same embedded-PostgreSQL database as
the business schema (one ``erudi`` database, one cluster backup captures
everything). The LangGraph-managed tables (``checkpoints``,
``checkpoint_writes``, …) live side by side with the SQLAlchemy tables but are
owned exclusively by the saver.

The saver is held open for the whole application lifetime (FastAPI
``lifespan`` enters the CM on startup and exits it on shutdown, BEFORE the
cluster stops) and exposed on ``app.state.checkpointer``; endpoints reach it
via ``get_checkpointer``. In tests the ``client`` fixture injects an
``InMemorySaver``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.core.logging import logger


@asynccontextmanager
async def open_checkpointer(conn_string: str) -> AsyncIterator[AsyncPostgresSaver]:
    """Open an ``AsyncPostgresSaver`` held for the whole app lifetime.

    ``AsyncPostgresSaver.from_conn_string`` is itself an async context manager
    that CLOSES its psycopg connection on ``__aexit__``, so we wrap it and keep
    it entered across the lifespan (the lifespan enters this CM manually and
    exits it on shutdown). ``setup()`` creates/migrates the LangGraph tables
    (idempotent).

    Args:
        conn_string: Raw psycopg URI (``postgresql://…`` — NOT the
            ``postgresql+psycopg://`` SQLAlchemy form), e.g.
            ``PostgresHandle.psycopg_url``.

    Yields a ready-to-use saver.
    """
    async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
        await saver.setup()  # creates/migrates LangGraph tables (idempotent)
        logger.info("Conversation checkpointer ready (PostgreSQL)")
        yield saver


def get_checkpointer(request: Request) -> BaseCheckpointSaver:
    """FastAPI dependency returning the app-wide checkpointer from ``app.state``.

    Set during ``lifespan`` startup (``AsyncPostgresSaver``). In tests the
    ``client`` fixture injects an ``InMemorySaver`` onto
    ``app.state.checkpointer``.
    """
    return request.app.state.checkpointer
