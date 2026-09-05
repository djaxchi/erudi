"""Gap coverage for the embedded-Postgres watchdog (#162) on top of
`test_db_watchdog.py`.

Pins the thread-safe wake signalling, listener attach/detach edge cases,
the tenant re-bind helpers (checkpointer / KB store), a full mocked
resurrection attempt with the backoff ladder, the wake-wait primitive, and
the recovery loop's state transitions including its never-die error guard.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core import config
from src.database import core as db_core
from src.launcher import db_watchdog as wd


@pytest.fixture(autouse=True)
def _reset_watchdog_state(monkeypatch):
    """Isolate module-global watchdog state per test."""
    monkeypatch.setattr(wd, "_app", None)
    monkeypatch.setattr(wd, "_loop_task", None)
    monkeypatch.setattr(wd, "_wake", None)
    monkeypatch.setattr(wd, "_event_loop", None)
    monkeypatch.setattr(wd, "_listener_engine", None)
    monkeypatch.setattr(wd, "db_state", wd.DB_OK)
    yield


# =====================================================================
# UNIT - wake signalling
# =====================================================================


@pytest.mark.unit
class TestSignalWake:
    def test_noop_without_loop(self):
        wd._signal_wake()  # loop/wake unset: nothing to do, nothing to raise

    async def test_sets_event_via_running_loop(self, monkeypatch):
        wake = asyncio.Event()
        monkeypatch.setattr(wd, "_wake", wake)
        monkeypatch.setattr(wd, "_event_loop", asyncio.get_running_loop())
        wd._signal_wake()
        await asyncio.sleep(0)  # let call_soon_threadsafe land
        assert wake.is_set()

    def test_closed_loop_is_swallowed(self, monkeypatch):
        loop = MagicMock()
        loop.call_soon_threadsafe.side_effect = RuntimeError("Event loop is closed")
        monkeypatch.setattr(wd, "_wake", MagicMock())
        monkeypatch.setattr(wd, "_event_loop", loop)
        wd._signal_wake()  # must not raise during shutdown


# =====================================================================
# UNIT - listener lifecycle edge cases
# =====================================================================


@pytest.mark.unit
class TestListenerLifecycle:
    def test_register_is_idempotent_for_same_engine(self, monkeypatch, test_db_engine):
        monkeypatch.setattr(db_core, "db_engine", test_db_engine)
        try:
            wd._register_error_listener()
            assert wd._listener_engine is test_db_engine
            wd._register_error_listener()  # same engine: early no-op
            assert wd._listener_engine is test_db_engine
        finally:
            wd._remove_error_listener()

    def test_remove_swallows_stale_engine(self, monkeypatch):
        # A disposed/foreign object makes event.remove blow up; best effort.
        monkeypatch.setattr(wd, "_listener_engine", object())
        wd._remove_error_listener()
        assert wd._listener_engine is None


# =====================================================================
# UNIT - probe without an engine
# =====================================================================


@pytest.mark.unit
class TestProbe:
    def test_probe_sync_requires_engine(self, monkeypatch):
        monkeypatch.setattr(db_core, "db_engine", None)
        with pytest.raises(RuntimeError, match="not initialized"):
            wd._probe_sync()


# =====================================================================
# UNIT - tenant re-bind helpers
# =====================================================================


class _FakeCheckpointerCM:
    def __init__(self, saver="new-saver", fail_exit=False):
        self.saver = saver
        self.fail_exit = fail_exit
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.saver

    async def __aexit__(self, *exc):
        self.exited = True
        if self.fail_exit:
            raise RuntimeError("stale connection refused to close")


@pytest.mark.unit
class TestRebindHelpers:
    async def test_rebind_checkpointer_noop_without_app(self):
        await wd._rebind_checkpointer(SimpleNamespace(psycopg_url="postgresql://x"))

    async def test_rebind_checkpointer_swaps_saver_then_closes_old(self, monkeypatch):
        old_cm = _FakeCheckpointerCM(saver="old-saver")
        new_cm = _FakeCheckpointerCM(saver="new-saver")
        app = SimpleNamespace(
            state=SimpleNamespace(checkpointer="old-saver", checkpointer_cm=old_cm)
        )
        monkeypatch.setattr(wd, "_app", app)
        monkeypatch.setattr(wd, "open_checkpointer", lambda url: new_cm)

        await wd._rebind_checkpointer(SimpleNamespace(psycopg_url="postgresql://y"))

        assert app.state.checkpointer == "new-saver"
        assert app.state.checkpointer_cm is new_cm
        assert old_cm.exited is True

    async def test_rebind_checkpointer_tolerates_stale_close_failure(self, monkeypatch):
        old_cm = _FakeCheckpointerCM(fail_exit=True)
        new_cm = _FakeCheckpointerCM(saver="fresh")
        app = SimpleNamespace(state=SimpleNamespace(checkpointer=None, checkpointer_cm=old_cm))
        monkeypatch.setattr(wd, "_app", app)
        monkeypatch.setattr(wd, "open_checkpointer", lambda url: new_cm)

        await wd._rebind_checkpointer(SimpleNamespace(psycopg_url="postgresql://y"))

        assert app.state.checkpointer == "fresh"  # new saver live despite the error

    def test_rebind_kb_store_updates_app_state(self, monkeypatch):
        closed = []
        monkeypatch.setattr(wd, "close_kb_store", lambda: closed.append(True))
        monkeypatch.setattr(wd, "init_kb_store", lambda handle: "fresh-store")
        app = SimpleNamespace(state=SimpleNamespace(kb_store=None))
        monkeypatch.setattr(wd, "_app", app)

        wd._rebind_kb_store(SimpleNamespace())

        assert closed == [True]
        assert app.state.kb_store == "fresh-store"


# =====================================================================
# UNIT - resurrection attempt + backoff ladder
# =====================================================================


@pytest.mark.unit
class TestResurrection:
    def _wire_success(self, monkeypatch, tmp_path):
        handle = SimpleNamespace(
            sqlalchemy_url="postgresql+psycopg://u", psycopg_url="postgresql://u"
        )
        monkeypatch.setattr(config, "POSTGRES_DATA_DIR", tmp_path, raising=False)
        monkeypatch.setattr(wd, "_evict_pgserver_cache", lambda d: None)
        monkeypatch.setattr(wd, "start_postgres", lambda d: handle)
        monkeypatch.setattr(wd, "init_database", lambda url: None)
        monkeypatch.setattr(wd, "_register_error_listener", lambda: None)

        async def rebind_cp(h):
            return None

        monkeypatch.setattr(wd, "_rebind_checkpointer", rebind_cp)
        monkeypatch.setattr(wd, "_rebind_kb_store", lambda h: None)
        monkeypatch.setattr(wd, "_probe_sync", lambda: None)
        return handle

    async def test_successful_attempt_rebinds_and_stores_handle(self, monkeypatch, tmp_path):
        handle = self._wire_success(monkeypatch, tmp_path)
        app = SimpleNamespace(state=SimpleNamespace(postgres=None))
        monkeypatch.setattr(wd, "_app", app)

        assert await wd._resurrect_once(1) is True
        assert app.state.postgres is handle

    async def test_failed_attempt_returns_false(self, monkeypatch, tmp_path):
        self._wire_success(monkeypatch, tmp_path)

        def broken_start(data_dir):
            raise RuntimeError("port exhausted")

        monkeypatch.setattr(wd, "start_postgres", broken_start)
        assert await wd._resurrect_once(1) is False

    async def test_episode_recovers_on_first_success(self, monkeypatch):
        async def resurrect(attempt):
            return True

        monkeypatch.setattr(wd, "_resurrect_once", resurrect)
        monkeypatch.setattr(wd, "db_state", wd.DB_RECOVERING)
        await wd._run_recovery_episode()
        assert wd.db_state == wd.DB_OK

    async def test_episode_parks_failed_after_ladder(self, monkeypatch):
        attempts = []

        async def resurrect(attempt):
            attempts.append(attempt)
            return False

        async def instant_sleep(delay):
            return None

        monkeypatch.setattr(wd, "_resurrect_once", resurrect)
        monkeypatch.setattr(wd.asyncio, "sleep", instant_sleep)
        monkeypatch.setattr(wd, "db_state", wd.DB_RECOVERING)
        await wd._run_recovery_episode()
        assert attempts == [1, 2, 3]
        assert wd.db_state == wd.DB_FAILED


# =====================================================================
# UNIT - wake-wait primitive
# =====================================================================


@pytest.mark.unit
class TestWaitWake:
    async def test_without_event_sleeps_and_reports_timeout(self, monkeypatch):
        assert await wd._wait_wake(0.01) is False

    async def test_woken_event_returns_true_and_clears(self, monkeypatch):
        wake = asyncio.Event()
        wake.set()
        monkeypatch.setattr(wd, "_wake", wake)
        assert await wd._wait_wake(0.5) is True
        assert not wake.is_set()

    async def test_timeout_returns_false(self, monkeypatch):
        monkeypatch.setattr(wd, "_wake", asyncio.Event())
        assert await wd._wait_wake(0.01) is False


# =====================================================================
# INTEGRATION - loop state machine via start/stop
# =====================================================================


@pytest.mark.integration
class TestRecoveryLoop:
    async def test_loop_probes_recovers_and_rearms(self, monkeypatch, test_db_engine):
        probes = []
        episodes = []

        async def fake_probe():
            probes.append(True)

        async def fake_episode():
            episodes.append(True)
            monkeypatch.setattr(wd, "db_state", wd.DB_OK)

        monkeypatch.setattr(wd, "_PROBE_INTERVAL_SECONDS", 0.02)
        monkeypatch.setattr(wd, "_probe_ok", fake_probe)
        monkeypatch.setattr(wd, "_run_recovery_episode", fake_episode)
        monkeypatch.setattr(db_core, "db_engine", test_db_engine)

        app = SimpleNamespace(state=SimpleNamespace())
        wd.start_watchdog(app)
        try:
            wd.start_watchdog(app)  # idempotent while running
            await asyncio.sleep(0.06)
            assert probes, "healthy loop must run the proactive probe"

            # Reactive path: flag down -> the loop runs a recovery episode
            wd._flag_down("test-injected failure")
            await asyncio.sleep(0.06)
            assert episodes, "recovering state must trigger an episode"
            assert wd.get_db_state() == wd.DB_OK

            # Parked path: failed state re-arms to recovering on the next wake
            monkeypatch.setattr(wd, "db_state", wd.DB_FAILED)
            wd._signal_wake()
            await asyncio.sleep(0.06)
            assert len(episodes) >= 2, "re-armed park must retry recovery"
        finally:
            await wd.stop_watchdog()

    async def test_loop_survives_internal_errors(self, monkeypatch, test_db_engine):
        calls = []

        async def flaky_wait(timeout):
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError("spurious loop error")
            # A real suspension point: without it the patched loop would spin
            # without ever yielding control back to the test coroutine.
            await asyncio.sleep(0.02)
            return False

        async def fake_probe():
            return None

        monkeypatch.setattr(wd, "_wait_wake", flaky_wait)
        monkeypatch.setattr(wd, "_probe_ok", fake_probe)
        monkeypatch.setattr(db_core, "db_engine", test_db_engine)

        wd.start_watchdog(SimpleNamespace(state=SimpleNamespace()))
        try:
            # First iteration raises inside the loop; the guard sleeps 1s and
            # the loop must come back for a second _wait_wake call.
            for _ in range(30):
                if len(calls) >= 2:
                    break
                await asyncio.sleep(0.05)
            assert len(calls) >= 2, "loop must keep running after an internal error"
        finally:
            await wd.stop_watchdog()
