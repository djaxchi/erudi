"""Alembic migration guards (#96).

These spin their OWN throwaway pgserver cluster because they mutate the schema
(the session-scoped cluster is shared and migrated to head once). Two guarantees:

1. ``run_migrations`` on a fresh DB brings it to head AND the migration chain
   stays in sync with the SQLAlchemy models (``alembic check`` finds no diff).
2. ``run_migrations`` on a pre-Alembic DB (created by ``create_all``, no
   ``alembic_version``) ADOPTS it by stamping the baseline — it must not replay
   the baseline's CREATE TABLEs (which would collide) and must keep the data.
"""

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from src.database.core import Base
from src.database.migrations import (
    BASELINE_REVISION,
    _alembic_config,
    run_migrations,
)
from src.launcher.postgres_runtime import start_postgres, stop_postgres


def _alembic_version(url: str) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            if not inspect(conn).has_table("alembic_version"):
                return None
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        engine.dispose()


@pytest.fixture
def fresh_cluster(tmp_path_factory):
    handle = start_postgres(tmp_path_factory.mktemp("pg-migrations"))
    try:
        yield handle
    finally:
        stop_postgres(handle)


@pytest.mark.integration
def test_fresh_db_upgrades_to_head_and_matches_models(fresh_cluster):
    url = fresh_cluster.sqlalchemy_url

    run_migrations(url)

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert "llms" in tables and "conversations" in tables
    assert _alembic_version(url) == BASELINE_REVISION

    # The migration chain must equal the models: autogenerate detects no diff.
    # command.check raises CommandError if the schema drifts from Base.metadata.
    command.check(_alembic_config(url))


@pytest.mark.integration
def test_pre_alembic_db_is_stamped_not_replayed(fresh_cluster):
    url = fresh_cluster.sqlalchemy_url

    # Simulate a database created by the old create_all path: full schema, but no
    # alembic_version table.
    engine = create_engine(url)
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()
    assert _alembic_version(url) is None

    # Must STAMP the baseline (no CREATE TABLE collision), then be at head.
    run_migrations(url)

    assert _alembic_version(url) == BASELINE_REVISION
    engine = create_engine(url)
    try:
        assert "llms" in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
