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

from src.database.backup import backup_database, backups_dir_for
from src.database.core import Base
from src.database.migrations import (
    BASELINE_REVISION,
    _alembic_config,
    _head_revision,
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
    # Nest the data dir one level down so backups_dir_for (data_dir.parent/db-backups)
    # is unique per test — mktemp dirs otherwise share a parent and leak snapshots.
    base = tmp_path_factory.mktemp("pg-migrations")
    handle = start_postgres(base / "data")
    try:
        yield handle
    finally:
        stop_postgres(handle)


@pytest.mark.integration
def test_fresh_db_upgrades_to_head_and_matches_models(fresh_cluster):
    url = fresh_cluster.sqlalchemy_url

    run_migrations(fresh_cluster)

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert "llms" in tables and "conversations" in tables
    # training_jobs was dropped by revision 7bc061d58b4e (dead fine-tuning code).
    assert "training_jobs" not in tables
    assert _alembic_version(url) == _head_revision(_alembic_config(url))

    # The migration chain must equal the models: autogenerate detects no diff.
    # command.check raises CommandError if the schema drifts from Base.metadata.
    command.check(_alembic_config(url))


@pytest.mark.integration
def test_pre_alembic_db_is_stamped_not_replayed(fresh_cluster):
    url = fresh_cluster.sqlalchemy_url

    # Simulate a database created by the old create_all path: the FULL historical
    # schema (including the since-dropped training_jobs) but no alembic_version
    # table. Build it from the baseline revision, then strip alembic_version so it
    # looks pre-Alembic — Base.metadata.create_all no longer carries training_jobs
    # and so cannot stand in for the schema the drop migration expects.
    cfg = _alembic_config(url)
    command.upgrade(cfg, BASELINE_REVISION)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE alembic_version"))
        assert inspect(engine).has_table("training_jobs")
    finally:
        engine.dispose()
    assert _alembic_version(url) is None

    # Must STAMP the baseline (no CREATE TABLE collision), then apply newer
    # revisions to head — here, dropping training_jobs.
    run_migrations(fresh_cluster)

    assert _alembic_version(url) == _head_revision(cfg)
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert "llms" in tables
    assert "training_jobs" not in tables


@pytest.mark.integration
def test_backup_database_writes_a_dump(fresh_cluster):
    # pg_dump (custom format) of the LIVE cluster produces a non-empty snapshot.
    engine = create_engine(fresh_cluster.sqlalchemy_url)
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()

    dump = backup_database(fresh_cluster.psycopg_url, fresh_cluster.data_dir, label="baseline")

    assert dump.exists() and dump.stat().st_size > 0
    assert dump.parent == backups_dir_for(fresh_cluster.data_dir)


@pytest.mark.integration
def test_fresh_db_migration_takes_no_backup(fresh_cluster):
    # Nothing to lose on a fresh install -> run_migrations must not snapshot.
    run_migrations(fresh_cluster)

    backups = backups_dir_for(fresh_cluster.data_dir)
    assert not backups.exists() or not list(backups.glob("*.dump"))
