"""KB embedding-model gate (#146): availability is filesystem-driven, download
is an idempotent background task, and the routes don't collide with the
parametric ``/{llm_id}/status`` KB route.
"""

import pytest

from src.ingestion import embedding_model as em


@pytest.fixture(autouse=True)
def _reset_state():
    em._reset_state_for_tests()
    yield
    em._reset_state_for_tests()


def _set_cached(monkeypatch, present: bool):
    monkeypatch.setattr(
        em,
        "try_to_load_from_cache",
        lambda *a, **k: "/cache/model.safetensors" if present else None,
    )


@pytest.mark.unit
def test_available_true_when_weights_cached(monkeypatch):
    _set_cached(monkeypatch, True)
    assert em.embedding_model_available() is True


@pytest.mark.unit
def test_available_false_when_weights_absent(monkeypatch):
    _set_cached(monkeypatch, False)
    assert em.embedding_model_available() is False


@pytest.mark.unit
def test_available_false_on_cached_no_exist_sentinel(monkeypatch):
    # huggingface_hub returns a non-str sentinel when it knows the file does not
    # exist; only a real str path counts as available.
    monkeypatch.setattr(em, "try_to_load_from_cache", lambda *a, **k: object())
    assert em.embedding_model_available() is False


@pytest.mark.unit
def test_download_state_shape(monkeypatch):
    _set_cached(monkeypatch, False)
    assert em.download_state() == {"available": False, "downloading": False, "error": None}


@pytest.mark.unit
def test_start_download_runs_load_when_absent(monkeypatch):
    _set_cached(monkeypatch, False)
    monkeypatch.setattr(em, "_spawn", lambda target: target())  # run synchronously
    calls = []
    monkeypatch.setattr(em, "_load_model", lambda: calls.append("loaded"))

    em.start_download()

    assert calls == ["loaded"]
    assert em._state["downloading"] is False  # finished
    assert em._state["error"] is None


@pytest.mark.unit
def test_start_download_noop_when_already_available(monkeypatch):
    _set_cached(monkeypatch, True)
    calls = []
    monkeypatch.setattr(em, "_spawn", lambda target: calls.append("spawned"))
    monkeypatch.setattr(em, "_load_model", lambda: calls.append("loaded"))

    state = em.start_download()

    assert calls == []  # already present -> never spawned
    assert state["available"] is True
    assert state["downloading"] is False


@pytest.mark.unit
def test_start_download_idempotent_when_already_downloading(monkeypatch):
    _set_cached(monkeypatch, False)
    em._reset_state_for_tests(downloading=True)
    calls = []
    monkeypatch.setattr(em, "_spawn", lambda target: calls.append("spawned"))

    em.start_download()

    assert calls == []  # a download is already in flight -> no second task


@pytest.mark.unit
def test_download_error_is_surfaced(monkeypatch):
    _set_cached(monkeypatch, False)
    monkeypatch.setattr(em, "_spawn", lambda target: target())

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(em, "_load_model", boom)

    em.start_download()

    assert em._state["downloading"] is False
    assert "network down" in (em._state["error"] or "")


@pytest.mark.unit
def test_embedding_model_routes_do_not_collide_with_llm_id_status(monkeypatch):
    # GET /knowledge_base/embedding-model/status must resolve to the gate route,
    # NOT be captured by the parametric GET /knowledge_base/{llm_id}/status
    # (which would 422 trying to parse "embedding-model" as an int).
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.domains.knowledge_base.endpoints import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    monkeypatch.setattr(em, "try_to_load_from_cache", lambda *a, **k: None)
    resp = client.get("/knowledge_base/embedding-model/status")

    assert resp.status_code == 200
    assert resp.json() == {"available": False, "downloading": False, "error": None}
