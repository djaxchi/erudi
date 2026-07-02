"""P1 tests — embedded PostgreSQL runtime (pgserver) + explicit database init.

Covers:
- start_postgres(): cluster boot, `erudi` database creation, pgvector extension,
  the two URL forms (SQLAlchemy + raw psycopg), idempotent restart.
- stop_postgres(): explicit shutdown.
- init_database(): explicit engine creation + SessionLocal binding, and the
  anti-B1 rule (create_tables must not rely on an imported-by-value engine).
"""

import subprocess

import psycopg
import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text

from src.launcher import postgres_runtime
from src.launcher.postgres_runtime import (
    _recover_corrupt_pgdata,
    start_postgres,
    stop_postgres,
)


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

    @pytest.mark.integration
    def test_stale_handle_pids_are_pruned(self, tmp_path_factory):
        """pgserver refcounts cluster users in <pgdata>/.handle_pids.json but
        never prunes dead pids: a crashed/SIGKILLed backend leaves a ghost
        entry that makes every later cleanup() skip the server stop forever.
        start_postgres must prune dead pids so the last live handle really
        stops the cluster."""
        import json
        import os
        import signal
        import subprocess

        data_dir = tmp_path_factory.mktemp("pgdata-prune")
        try:
            first = start_postgres(data_dir)
            stop_postgres(first)

            # Simulate a previous owner that died brutally (pid is real but dead).
            ghost = subprocess.Popen(["sleep", "0"])
            ghost.wait()
            (data_dir / ".handle_pids.json").write_text(json.dumps([ghost.pid]))

            handle = start_postgres(data_dir)
            stop_postgres(handle)

            # Without pruning, the ghost pid would block the stop and the
            # postmaster would survive (postmaster.pid still present).
            assert not (data_dir / "postmaster.pid").exists()
        finally:
            # The red scenario is precisely "the stop is skipped": never leak
            # a live postmaster on the dev machine when this test regresses.
            pid_file = data_dir / "postmaster.pid"
            if pid_file.exists():
                os.kill(int(pid_file.read_text().splitlines()[0]), signal.SIGTERM)


class TestCorruptPgdataRecovery:
    """#145 — a half-initialized pgdata (no PG_VERSION) must not brick boot."""

    @pytest.mark.unit
    def test_recover_leaves_initialized_cluster_untouched(self, tmp_path):
        (tmp_path / "PG_VERSION").write_text("16\n")
        (tmp_path / "base").mkdir()
        _recover_corrupt_pgdata(tmp_path)
        assert (tmp_path / "PG_VERSION").exists()
        assert (tmp_path / "base").exists()

    @pytest.mark.unit
    def test_recover_wipes_partial_dir_without_pg_version(self, tmp_path):
        (tmp_path / "junk.tmp").write_text("x")
        (tmp_path / "global").mkdir()
        (tmp_path / "global" / "leftover").write_text("y")
        assert list(tmp_path.iterdir())  # non-empty, no PG_VERSION
        _recover_corrupt_pgdata(tmp_path)
        assert list(tmp_path.iterdir()) == []  # wiped clean

    @pytest.mark.unit
    def test_recover_noop_on_empty_dir(self, tmp_path):
        _recover_corrupt_pgdata(tmp_path)  # must not raise
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.integration
    def test_start_postgres_recovers_from_missing_pg_version(self, tmp_path_factory):
        import os
        import signal

        data_dir = tmp_path_factory.mktemp("pgdata-recover")
        try:
            first = start_postgres(data_dir)
            stop_postgres(first)

            # Simulate an initdb interrupted before PG_VERSION was written:
            # the dir is populated but has no PG_VERSION. Without recovery,
            # pgserver's initdb would refuse the non-empty directory.
            (data_dir / "PG_VERSION").unlink()
            assert list(data_dir.iterdir())  # still populated

            handle = start_postgres(data_dir)
            try:
                assert (data_dir / "PG_VERSION").exists()  # re-initialized
                with psycopg.connect(handle.psycopg_url, autocommit=True) as conn:
                    assert conn.execute("SELECT 1").fetchone()[0] == 1
            finally:
                stop_postgres(handle)
        finally:
            pid_file = data_dir / "postmaster.pid"
            if pid_file.exists():
                os.kill(int(pid_file.read_text().splitlines()[0]), signal.SIGTERM)


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


class FakePostmaster:
    """Minimal stand-in for pgserver's PostmasterInfo readiness view."""

    def __init__(self, running, status):
        self._running = running
        self.status = status

    def is_running(self):
        return self._running


class TestRecoverySecondChance:
    """#161 — survive a slow WAL crash-recovery past pgserver's 10s pg_ctl timeout.

    Pure-unit: no real cluster. The postmaster/pgserver/time surfaces are
    monkeypatched on the postgres_runtime module so the second-chance logic can
    be exercised deterministically.
    """

    @pytest.mark.unit
    def test_wait_for_postmaster_ready_polls_until_ready(self, tmp_path, monkeypatch):
        # None (no pidfile yet) -> running but still recovering -> ready.
        sequence = [
            None,
            FakePostmaster(running=True, status="starting"),
            FakePostmaster(running=True, status="ready"),
        ]
        monkeypatch.setattr(
            postgres_runtime.PostmasterInfo,
            "read_from_pgdata",
            lambda data_dir: sequence.pop(0),
        )
        monkeypatch.setattr(postgres_runtime.time, "sleep", lambda _s: None)
        phases = []
        monkeypatch.setattr(postgres_runtime, "emit_phase", phases.append)

        assert postgres_runtime._wait_for_postmaster_ready(tmp_path, 90) is True
        # The wait announced itself so the renderer can label the pause.
        assert phases == ["recovering_database"]
        assert sequence == []  # consumed exactly through the ready reading

    @pytest.mark.unit
    def test_wait_for_postmaster_ready_times_out(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            postgres_runtime.PostmasterInfo,
            "read_from_pgdata",
            lambda data_dir: None,  # never comes up
        )
        monkeypatch.setattr(postgres_runtime.time, "sleep", lambda _s: None)
        monkeypatch.setattr(postgres_runtime, "emit_phase", lambda _p: None)

        # Tiny deadline + no-op sleep -> the loop bails almost immediately.
        assert postgres_runtime._wait_for_postmaster_ready(tmp_path, 0.01) is False

    @pytest.mark.unit
    def test_get_server_with_recovery_retries_after_timeout(self, tmp_path, monkeypatch):
        sentinel = object()
        calls = {"n": 0}

        def fake_get_server(path):
            calls["n"] += 1
            if calls["n"] == 1:
                raise subprocess.TimeoutExpired(cmd="pg_ctl", timeout=10)
            return sentinel  # second call reuses the recovered postmaster

        monkeypatch.setattr(postgres_runtime.pgserver, "get_server", fake_get_server)
        monkeypatch.setattr(
            postgres_runtime, "_wait_for_postmaster_ready", lambda d, s: True
        )

        assert postgres_runtime._get_server_with_recovery(tmp_path) is sentinel
        assert calls["n"] == 2  # first timed out, second reused the live postmaster

    @pytest.mark.unit
    def test_get_server_with_recovery_reraises_when_wait_fails(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        def fake_get_server(path):
            calls["n"] += 1
            raise subprocess.TimeoutExpired(cmd="pg_ctl", timeout=10)

        monkeypatch.setattr(postgres_runtime.pgserver, "get_server", fake_get_server)
        monkeypatch.setattr(
            postgres_runtime, "_wait_for_postmaster_ready", lambda d, s: False
        )

        with pytest.raises(subprocess.TimeoutExpired):
            postgres_runtime._get_server_with_recovery(tmp_path)
        assert calls["n"] == 1  # never retried get_server after the wait failed
