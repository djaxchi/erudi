"""Programmatic Alembic runner for the embedded PostgreSQL cluster.

The embedded cluster's data dir is persistent and survives app updates, so the
on-disk schema must be reconciled to the models on every startup. This applies
forward-only Alembic revisions (lifespan, after ``init_database``), replacing the
old ``Base.metadata.create_all`` path which could never add a column/table to an
already-existing database.

Transition handling (adopting Alembic on a live install base): a database created
by the pre-Alembic ``create_all`` path holds the business tables but has no
``alembic_version`` table. Replaying the baseline there would fail (its
``CREATE TABLE`` collides with the existing tables), so such a database is
**stamped** to the baseline first; ``upgrade head`` then applies anything newer.
A fresh (empty) database simply runs ``upgrade head`` from zero.
"""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from src.core.config import ROOT_DIR
from src.core.logging import logger

# The root revision (see alembic/versions/…_baseline_schema.py). A pre-Alembic
# database already matches this schema, so it is stamped to this revision.
BASELINE_REVISION = "5ac171e299c6"

# A business table present in ANY pre-Alembic database (created by create_all).
# Its presence without an alembic_version table signals "adopt at baseline".
_SENTINEL_TABLE = "llms"


def _alembic_config(sqlalchemy_url: str) -> Config:
    """Build a Config bound to the live cluster, resolved against ROOT_DIR.

    ROOT_DIR is the backend root in dev and the bundle root when frozen; both
    ship ``alembic.ini`` + ``alembic/`` there (see the PyInstaller specs). Paths
    are set explicitly so resolution never depends on the process cwd.
    """
    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)
    # Do NOT let env.py's fileConfig reconfigure (and disable) the app's loggers.
    cfg.attributes["configure_logger"] = False
    return cfg


def run_migrations(sqlalchemy_url: str) -> None:
    """Bring the database schema to head.

    Synchronous (Alembic is sync) — call via ``run_in_threadpool`` from the async
    lifespan so it does not block the event loop.
    """
    cfg = _alembic_config(sqlalchemy_url)
    engine = create_engine(sqlalchemy_url)
    try:
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
            has_business_tables = inspect(conn).has_table(_SENTINEL_TABLE)

        if current is None and has_business_tables:
            logger.info(
                "Existing pre-Alembic schema detected — stamping baseline %s",
                BASELINE_REVISION,
            )
            command.stamp(cfg, BASELINE_REVISION)

        command.upgrade(cfg, "head")
        logger.info("Database schema is at head")
    finally:
        engine.dispose()
