"""Embedded PostgreSQL runtime (pgserver) lifecycle for Erudi.

Starts/stops the local cluster bundled by the `pgserver` wheel (no Docker, no
system install), ensures the `erudi` database and the pgvector extension
exist, and derives the two URL forms consumed by the stack:

- ``sqlalchemy_url`` — ``postgresql+psycopg://…`` for the sync SQLAlchemy
  engine (business layer) and langchain-postgres ``PGEngine``.
- ``psycopg_url`` — ``postgresql://…`` for ``AsyncPostgresSaver`` and raw
  psycopg connections.

pgserver defaults to a Unix-domain-socket URI (``…?host=<socket dir>``) on
POSIX; ``get_server`` is idempotent (initdb on first run, refcounted across
processes) and registers an atexit cleanup. We still stop the cluster
explicitly from the FastAPI lifespan shutdown for a deterministic order
(checkpointer first, cluster last).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pgserver
import psycopg

from src.core.logging import logger

DB_NAME = "erudi"


@dataclass(frozen=True)
class PostgresHandle:
    """Live embedded-cluster handle with the two derived connection URLs."""

    server: "pgserver.PostgresServer"
    data_dir: Path
    psycopg_url: str
    sqlalchemy_url: str


def _uri_for_db(base_uri: str, dbname: str) -> str:
    """Swap the database name in a pgserver URI (``…/postgres?host=…``)."""
    head, _, query = base_uri.partition("?")
    head = head.rsplit("/", 1)[0] + f"/{dbname}"
    return f"{head}?{query}" if query else head


def start_postgres(data_dir: Path | str) -> PostgresHandle:
    """Boot (or join) the embedded cluster and make the `erudi` DB ready.

    Idempotent: safe to call on an already-initialized data dir or while the
    cluster is already running (pgserver refcounts users of the data dir).
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    server = pgserver.get_server(str(data_dir))
    admin_uri = server.get_uri()

    # CREATE DATABASE has no IF NOT EXISTS → guard on pg_database.
    # DB_NAME is an internal constant, never user input.
    with psycopg.connect(admin_uri, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{DB_NAME}"')

    psycopg_url = _uri_for_db(admin_uri, DB_NAME)

    # pgvector extensions are per-database → create inside `erudi`, not the
    # admin DB probed above.
    with psycopg.connect(psycopg_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    sqlalchemy_url = psycopg_url.replace("postgresql://", "postgresql+psycopg://", 1)
    logger.info(f"Embedded PostgreSQL ready (data_dir={data_dir})")
    return PostgresHandle(
        server=server,
        data_dir=data_dir,
        psycopg_url=psycopg_url,
        sqlalchemy_url=sqlalchemy_url,
    )


def stop_postgres(handle: PostgresHandle) -> None:
    """Stop the embedded cluster explicitly (deterministic shutdown order)."""
    handle.server.cleanup()
    logger.info("Embedded PostgreSQL stopped")
