"""The FastAPI lifespan emits startup-progress phases in order.

Fully mocked: every heavy startup dependency is stubbed, so this never touches
a real Postgres cluster. It verifies only that the lifespan surfaces the
`preparing_database → running_migrations → loading_catalog` phases (via the
`app.state.emit_phase` hook run.py injects) in the right order.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from src.core import api
from src.core import config


class _FakeEngine:
    def start_cleanup_task(self):
        pass

    def stop_cleanup_task(self):
        pass

    def cleanup(self):
        pass


class _FakeCheckpointerCM:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


@pytest.mark.unit
async def test_lifespan_emits_phases_in_order(monkeypatch):
    handle = SimpleNamespace(
        sqlalchemy_url="postgresql+psycopg://x/erudi",
        psycopg_url="postgresql://x/erudi",
    )

    monkeypatch.setattr(api, "start_postgres", lambda *_: handle)
    monkeypatch.setattr(api, "stop_postgres", lambda *_: None)
    monkeypatch.setattr(api, "init_database", lambda *_: None)
    monkeypatch.setattr(api, "run_migrations", lambda *_: None)
    monkeypatch.setattr(api, "init_kb_store", lambda *_: None)
    monkeypatch.setattr(api, "close_kb_store", lambda *_a, **_k: None)
    monkeypatch.setattr(api, "open_checkpointer", lambda *_: _FakeCheckpointerCM())

    async def _fake_populate():
        return {}  # falsy needs_background_refresh -> no background task

    monkeypatch.setattr(api, "startup_populate_database", _fake_populate)

    fake_base = SimpleNamespace(get_engine=lambda: _FakeEngine())
    monkeypatch.setattr(api, "BaseEngine", fake_base)
    monkeypatch.setattr(config, "LLM_Engine", None, raising=False)

    phases: list[str] = []
    app = FastAPI()
    app.state.emit_phase = phases.append

    async with api.lifespan(app):
        pass

    assert phases == ["preparing_database", "running_migrations", "loading_catalog"]


@pytest.mark.unit
async def test_lifespan_without_emitter_does_not_crash(monkeypatch):
    """No emit_phase on app.state (e.g. plain uvicorn in dev) -> phases skipped."""
    handle = SimpleNamespace(
        sqlalchemy_url="postgresql+psycopg://x/erudi",
        psycopg_url="postgresql://x/erudi",
    )
    monkeypatch.setattr(api, "start_postgres", lambda *_: handle)
    monkeypatch.setattr(api, "stop_postgres", lambda *_: None)
    monkeypatch.setattr(api, "init_database", lambda *_: None)
    monkeypatch.setattr(api, "run_migrations", lambda *_: None)
    monkeypatch.setattr(api, "init_kb_store", lambda *_: None)
    monkeypatch.setattr(api, "close_kb_store", lambda *_a, **_k: None)
    monkeypatch.setattr(api, "open_checkpointer", lambda *_: _FakeCheckpointerCM())

    async def _fake_populate():
        return {}

    monkeypatch.setattr(api, "startup_populate_database", _fake_populate)
    monkeypatch.setattr(api, "BaseEngine", SimpleNamespace(get_engine=lambda: _FakeEngine()))
    monkeypatch.setattr(config, "LLM_Engine", None, raising=False)

    app = FastAPI()  # no app.state.emit_phase
    async with api.lifespan(app):
        pass  # must not raise
