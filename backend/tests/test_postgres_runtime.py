"""P1 tests — embedded PostgreSQL runtime (pgserver) + explicit database init.

Covers:
- start_postgres(): cluster boot, `erudi` database creation, pgvector extension,
  the two URL forms (SQLAlchemy + raw psycopg), idempotent restart.
- stop_postgres(): explicit shutdown.
- init_database(): explicit engine creation + SessionLocal binding, and the
  anti-B1 rule (create_tables must not rely on an imported-by-value engine).
"""

import psycopg
import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text

from src.launcher.postgres_runtime import start_postgres, stop_postgres


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    """One throwaway embedded cluster for the whole module (boot is seconds)."""
    handle = start_postgres(tmp_path_factory.mktemp("pgdata-p1"))
    yield handle
    stop_postgres(handle)


class TestPostgresRuntime:
    @pytest.mark.integration
    def test_url_shapes(self, pg):
        assert pg.sqlalchemy_url.startswith("postgresql+psycopg://")
        assert pg.psycopg_url.startswith("postgresql://")
        assert "+psycopg" not in pg.psycopg_url

    @pytest.mark.integration
    def test_sqlalchemy_connects_to_erudi_database(self, pg):
        eng = create_engine(pg.sqlalchemy_url)
        try:
            with eng.connect() as conn:
                assert conn.execute(text("SELECT current_database()")).scalar() == "erudi"
        finally:
            eng.dispose()

    @pytest.mark.integration
    def test_vector_extension_installed_in_erudi_database(self, pg):
        eng = create_engine(pg.sqlalchemy_url)
        try:
            with eng.connect() as conn:
                names = {row[0] for row in conn.execute(text("SELECT extname FROM pg_extension"))}
        finally:
            eng.dispose()
        assert "vector" in names

    @pytest.mark.integration
    def test_psycopg_url_accepted_by_raw_psycopg(self, pg):
        with psycopg.connect(pg.psycopg_url, autocommit=True) as conn:
            assert conn.execute("SELECT 1").fetchone()[0] == 1

    @pytest.mark.integration
    def test_start_postgres_is_idempotent(self, pg):
        again = start_postgres(pg.data_dir)
        assert again.sqlalchemy_url == pg.sqlalchemy_url
        # Same cluster, still answering.
        with psycopg.connect(again.psycopg_url, autocommit=True) as conn:
            assert conn.execute("SELECT 1").fetchone()[0] == 1


class TestInitDatabase:
    @pytest.mark.integration
    async def test_init_database_binds_engine_and_session_factory(self, pg):
        from src.database import core

        try:
            engine = core.init_database(pg.sqlalchemy_url)
            assert engine is core.db_engine
            session = core.SessionLocal()
            try:
                assert session.execute(text("SELECT 1")).scalar() == 1
            finally:
                session.close()
        finally:
            core.SessionLocal.configure(bind=None)
            core.db_engine = None

    @pytest.mark.integration
    async def test_create_tables_works_after_init_database(self, pg):
        """Anti-B1: Database_Seeder.create_tables must read the LIVE engine,
        not a stale imported-by-value copy frozen at import time."""
        from src.database import core
        from src.database.seed import Database_Seeder

        try:
            engine = core.init_database(pg.sqlalchemy_url)
            await Database_Seeder().create_tables()
            tables = set(sa_inspect(engine).get_table_names())
            assert {"llms", "conversations", "messages"} <= tables
        finally:
            core.SessionLocal.configure(bind=None)
            core.db_engine = None

    @pytest.mark.integration
    async def test_create_tables_without_init_raises_explicit_error(self, pg):
        from src.database import core
        from src.database.seed import Database_Seeder

        assert core.db_engine is None  # process-fresh or reset by previous tests
        with pytest.raises(RuntimeError, match="init_database"):
            await Database_Seeder().create_tables()
