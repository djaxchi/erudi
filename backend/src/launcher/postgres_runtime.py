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

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pgserver
import pgserver.postgres_server as _pg_server_mod
import psutil
import psycopg
from pgserver.utils import PostmasterInfo
from pgserver.utils import find_suitable_socket_dir as _orig_find_socket_dir
from pgserver.utils import socket_name_length_ok

from src.core.logging import logger
from src.launcher.events import emit_phase

DB_NAME = "erudi"

# How long a WAL crash-recovery may take before we give up on the boot. Must
# stay under run.py's STARTUP_TIMEOUT_SECONDS (120s non-first-run) minus the
# ~25s of cold imports — a recovery never happens on first run (no WAL yet).
RECOVERY_WAIT_SECONDS = 90


def _space_safe_socket_dir(pgdata, runtime_path):
    """Choose a postgres unix-socket dir that contains no spaces.

    pgserver hands the socket dir to postgres via ``pg_ctl -o "-k <dir>"`` — a
    string postgres re-parses by splitting on whitespace, so a dir with a space
    (e.g. the macOS-idiomatic ``~/Library/Application Support/…``) breaks
    startup with ``postgres: invalid argument``. The DATA dir stays in the
    platform's idiomatic per-OS location (it is passed to ``-D`` as a list
    argument, which preserves spaces); only the ephemeral socket is relocated to
    a short, space-free temp dir — where unix sockets conventionally live. When
    pgdata has no space, pgserver's own logic is used unchanged.
    """
    pgdata = Path(pgdata)
    if " " not in str(pgdata):
        return _orig_find_socket_dir(pgdata, runtime_path)
    base = Path(tempfile.gettempdir())  # space-free on macOS/Windows/Linux
    digest = hashlib.sha256(f"{pgdata}-{pgdata.stat().st_ino}".encode()).hexdigest()[:10]
    socket_dir = base / f"erudi-pg-{digest}"
    socket_dir.mkdir(parents=True, exist_ok=True)
    if not socket_name_length_ok(socket_dir / ".s.PGSQL.5432"):
        return _orig_find_socket_dir(pgdata, runtime_path)
    logger.info(f"Using space-free postgres socket dir: {socket_dir}")
    return socket_dir


# pgserver looks this name up on its own module at call time, so patch there.
_pg_server_mod.find_suitable_socket_dir = _space_safe_socket_dir


def _prune_stale_handle_pids(data_dir: Path) -> None:
    """Drop dead pids from pgserver's per-cluster refcount registry.

    pgserver tracks cluster users in ``<pgdata>/.handle_pids.json`` but never
    prunes dead entries: a crashed/SIGKILLed backend leaves a ghost pid that
    makes every later ``cleanup()`` skip the server stop — forever. Pruning
    before joining the cluster guarantees the LAST live handle really stops
    the postmaster on graceful shutdown.
    """
    handle_file = data_dir / ".handle_pids.json"
    if not handle_file.exists():
        return
    try:
        pids = json.loads(handle_file.read_text() or "[]")
        alive = [pid for pid in pids if psutil.pid_exists(pid)]
        if alive != pids:
            handle_file.write_text(json.dumps(alive))
            logger.info(
                f"Pruned stale pgserver handle pids: {sorted(set(pids) - set(alive))}"
            )
    except (OSError, ValueError) as exc:
        # Unreadable/corrupt registry — pgserver will rebuild it on boot.
        logger.warning(f"Could not prune pgserver handle pids: {exc}")


def _recover_corrupt_pgdata(data_dir: Path) -> None:
    """Wipe a half-initialized data dir so pgserver can run a clean initdb.

    An interrupted first-run initdb (e.g. the launcher was killed mid-init by an
    over-eager watchdog) can leave the data dir populated but WITHOUT a
    ``PG_VERSION`` file. On the next boot ``initdb`` refuses a non-empty target
    directory, so every later launch fails permanently until the user manually
    deletes the folder. Detect that state and clear the directory before handing
    it to pgserver, which then initializes a fresh cluster. A dir that already
    has ``PG_VERSION`` is a real cluster and is left untouched; an empty dir is
    fine as-is.
    """
    if (data_dir / "PG_VERSION").exists():
        return  # a real, initialized cluster — never touch it
    try:
        entries = list(data_dir.iterdir())
    except OSError:
        return
    if not entries:
        return  # empty — pgserver will initdb into it cleanly
    logger.warning(
        f"Recovering half-initialized Postgres data dir (no PG_VERSION): {data_dir}"
    )
    for entry in entries:
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"Could not remove {entry} during pgdata recovery: {exc}")


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


def _wait_for_postmaster_ready(data_dir: Path, deadline_seconds: float) -> bool:
    """Wait for a background postmaster to finish WAL crash-recovery (#161).

    pgserver starts the cluster with ``pg_ctl -w start`` under a HARDCODED
    ``timeout=10`` and re-raises ``subprocess.TimeoutExpired`` when that wait
    elapses. But the timeout only kills the *waiter* (``pg_ctl``), not the
    postmaster it already spawned: after an unclean shutdown the postmaster keeps
    replaying the WAL in the background and typically comes up fine a little
    later. A slow recovery is not a failure, so we give the live postmaster a
    patient (bounded) second chance instead of crashing the boot.

    Readiness reuses pgserver's OWN predicate (its post-start wait loop):
    ``PostmasterInfo.read_from_pgdata`` reports a running server whose ``status``
    is ``ready``. Returns True once ready, False if the deadline expires.
    """
    emit_phase("recovering_database")
    logger.info(
        f"Waiting up to {deadline_seconds:.0f}s for Postgres crash recovery to "
        f"finish (data_dir={data_dir})"
    )
    start = time.monotonic()
    deadline = start + deadline_seconds
    while time.monotonic() < deadline:
        pinfo = PostmasterInfo.read_from_pgdata(data_dir)
        if pinfo is not None and pinfo.is_running() and pinfo.status == "ready":
            logger.info(
                f"Postgres crash recovery finished after "
                f"{time.monotonic() - start:.1f}s; reusing the recovered postmaster"
            )
            return True
        time.sleep(1.0)
    logger.warning(
        f"Postgres crash recovery did not report ready within {deadline_seconds:.0f}s"
    )
    return False


def _get_server_with_recovery(data_dir: Path):
    """Boot (or join) the cluster, tolerating a slow WAL crash-recovery (#161).

    ``pgserver.get_server`` starts the postmaster with ``pg_ctl -w`` under a
    hardcoded 10s timeout and re-raises ``subprocess.TimeoutExpired`` when the
    wait elapses. After an unclean shutdown the first boot must crash-recover,
    which routinely takes longer than 10s — yet the timeout only kills the
    ``pg_ctl`` waiter, not the postmaster, which keeps recovering in the
    background.

    Second-chance semantics: catch the timeout, wait (bounded) for the live
    postmaster to report ready, then call ``get_server`` again — it reuses the
    already-running postmaster without touching ``pg_ctl`` (a manual Retry
    minutes after such a crash booted in 1.3s through exactly that path). If the
    wait expires we re-raise the ORIGINAL error, preserving today's failure path
    after real patience and clear logs.
    """
    try:
        return pgserver.get_server(str(data_dir))
    except subprocess.TimeoutExpired:
        logger.warning(
            "pgserver's pg_ctl waiter gave up after its hardcoded 10s timeout; "
            "the postmaster is likely still WAL crash-recovering in the "
            "background - waiting for it to finish before retrying"
        )
        if _wait_for_postmaster_ready(data_dir, RECOVERY_WAIT_SECONDS):
            return pgserver.get_server(str(data_dir))
        raise


def start_postgres(data_dir: Path | str) -> PostgresHandle:
    """Boot (or join) the embedded cluster and make the `erudi` DB ready.

    Idempotent: safe to call on an already-initialized data dir or while the
    cluster is already running (pgserver refcounts users of the data dir).
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _prune_stale_handle_pids(data_dir)
    _recover_corrupt_pgdata(data_dir)

    server = _get_server_with_recovery(data_dir)
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
