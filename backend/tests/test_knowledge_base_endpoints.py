"""Tests for the Knowledge Base REST endpoints.

The service layer is covered by `test_knowledge_base_services.py`; this file
pins the HTTP layer: request validation, the create-vs-update decision tree,
error mapping to the structured exception responses, the embedding-model
gate endpoints (#146), and the background-task wrappers' session handling.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.domains.knowledge_base import endpoints as kb_endpoints
from src.domains.knowledge_base.services import KB_Service


def _payload(**overrides) -> dict:
    body = {
        "paths": ["/tmp/doc1.pdf"],
        "selectedModel": 1,
        "modelName": "Docs Assistant",
        "description": "test corpus",
    }
    body.update(overrides)
    return body


# =====================================================================
# INTEGRATION - embedding-model gate endpoints (#146)
# =====================================================================

@pytest.mark.integration
class TestEmbeddingModelEndpoints:

    def test_status_returns_download_state(self, client, monkeypatch):
        monkeypatch.setattr(
            kb_endpoints, "download_state", lambda: {"present": True, "status": "idle"}
        )
        resp = client.get("/erudi/knowledge_base/embedding-model/status")
        assert resp.status_code == 200
        assert resp.json() == {"present": True, "status": "idle"}

    def test_download_kicks_off_background_download(self, client, monkeypatch):
        monkeypatch.setattr(
            kb_endpoints, "start_download", lambda: {"status": "downloading"}
        )
        resp = client.post("/erudi/knowledge_base/embedding-model/download")
        assert resp.status_code == 200
        assert resp.json() == {"status": "downloading"}

    def test_embedding_model_is_not_captured_as_llm_id(self, client, monkeypatch):
        """Route ordering regression: 'embedding-model' must never 422 as llm_id."""
        monkeypatch.setattr(kb_endpoints, "download_state", lambda: {})
        resp = client.get("/erudi/knowledge_base/embedding-model/status")
        assert resp.status_code == 200


# =====================================================================
# INTEGRATION - GET /{llm_id}/status
# =====================================================================

@pytest.mark.integration
class TestKbJobStatus:

    def test_returns_service_payload(self, client):
        status = {"status": "processing", "status_updated_at": None, "error_message": None}
        with patch.object(KB_Service, "get_kb_job_status", return_value=status):
            resp = client.get("/erudi/knowledge_base/7/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    def test_unknown_job_maps_to_404(self, client):
        with patch.object(
            KB_Service, "get_kb_job_status", side_effect=ValueError("no job")
        ):
            resp = client.get("/erudi/knowledge_base/999/status")
        assert resp.status_code == 404

    def test_unexpected_error_maps_to_500(self, client):
        with patch.object(
            KB_Service, "get_kb_job_status", side_effect=RuntimeError("db down")
        ):
            resp = client.get("/erudi/knowledge_base/7/status")
        assert resp.status_code == 500


# =====================================================================
# INTEGRATION - POST /create
# =====================================================================

@pytest.mark.integration
class TestCreateKnowledgeBase:

    @pytest.fixture(autouse=True)
    def _no_background_ingestion(self, monkeypatch):
        """Replace the queued background tasks so no real ingestion runs."""
        self.creation_calls = []
        self.update_calls = []
        monkeypatch.setattr(
            kb_endpoints,
            "_run_kb_creation_task",
            lambda **kw: self.creation_calls.append(kw),
        )
        monkeypatch.setattr(
            kb_endpoints,
            "_run_kb_update_task",
            lambda **kw: self.update_calls.append(kw),
        )

    def test_empty_paths_rejected(self, client):
        resp = client.post(
            "/erudi/knowledge_base/create", json=_payload(paths=[])
        )
        assert resp.status_code == 422

    def test_empty_model_name_rejected(self, client):
        resp = client.post(
            "/erudi/knowledge_base/create", json=_payload(modelName="")
        )
        assert resp.status_code == 422

    def test_missing_base_llm_maps_to_404(self, client):
        resp = client.post(
            "/erudi/knowledge_base/create", json=_payload(selectedModel=987654)
        )
        assert resp.status_code == 404

    def test_creates_new_assistant_for_unattached_base(self, client, mock_llm):
        with patch.object(
            KB_Service, "create_kb_assistant", return_value=(41, 9)
        ) as create:
            resp = client.post(
                "/erudi/knowledge_base/create",
                json=_payload(selectedModel=mock_llm.id),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == 41
        assert "created" in body["msg"]
        create.assert_called_once()
        assert self.creation_calls == [
            {"kb_job_id": 9, "file_paths": ["/tmp/doc1.pdf"]}
        ]
        assert self.update_calls == []

    def test_updates_existing_kb_for_attached_base(self, client, mock_llm_with_kb):
        llm, _kb = mock_llm_with_kb
        with patch.object(
            KB_Service, "update_existing_kb", return_value=(llm.id, 12)
        ) as update:
            resp = client.post(
                "/erudi/knowledge_base/create", json=_payload(selectedModel=llm.id)
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_id"] == llm.id
        assert "updated" in body["msg"]
        update.assert_called_once()
        assert self.update_calls == [
            {"kb_job_id": 12, "file_paths": ["/tmp/doc1.pdf"]}
        ]
        assert self.creation_calls == []

    def test_service_valueerror_maps_to_404(self, client, mock_llm):
        with patch.object(
            KB_Service, "create_kb_assistant", side_effect=ValueError("gone")
        ):
            resp = client.post(
                "/erudi/knowledge_base/create",
                json=_payload(selectedModel=mock_llm.id),
            )
        assert resp.status_code == 404

    def test_unexpected_error_maps_to_500(self, client, mock_llm):
        with patch.object(
            KB_Service, "create_kb_assistant", side_effect=RuntimeError("io error")
        ):
            resp = client.post(
                "/erudi/knowledge_base/create",
                json=_payload(selectedModel=mock_llm.id),
            )
        assert resp.status_code == 500


# =====================================================================
# UNIT - background task wrappers
# =====================================================================

@pytest.mark.unit
class TestBackgroundTaskWrappers:

    def _fake_session(self, monkeypatch):
        session = MagicMock()
        monkeypatch.setattr(kb_endpoints, "SessionLocal", lambda: session)
        return session

    def test_creation_task_processes_and_closes_session(self, monkeypatch):
        session = self._fake_session(monkeypatch)
        with patch.object(KB_Service, "process_and_index_documents") as proc:
            kb_endpoints._run_kb_creation_task(kb_job_id=3, file_paths=["/tmp/a.txt"])
        proc.assert_called_once_with(
            db=session, kb_job_id=3, file_paths=["/tmp/a.txt"], is_update=False
        )
        session.close.assert_called_once()

    def test_update_task_processes_with_update_flag(self, monkeypatch):
        session = self._fake_session(monkeypatch)
        with patch.object(KB_Service, "process_and_index_documents") as proc:
            kb_endpoints._run_kb_update_task(kb_job_id=4, file_paths=["/tmp/b.txt"])
        proc.assert_called_once_with(
            db=session, kb_job_id=4, file_paths=["/tmp/b.txt"], is_update=True
        )
        session.close.assert_called_once()

    def test_creation_task_swallows_errors_but_closes_session(self, monkeypatch):
        session = self._fake_session(monkeypatch)
        with patch.object(
            KB_Service,
            "process_and_index_documents",
            side_effect=RuntimeError("ingestion blew up"),
        ):
            kb_endpoints._run_kb_creation_task(kb_job_id=5, file_paths=["/tmp/c.txt"])
        session.close.assert_called_once()

    def test_update_task_swallows_errors_but_closes_session(self, monkeypatch):
        session = self._fake_session(monkeypatch)
        with patch.object(
            KB_Service,
            "process_and_index_documents",
            side_effect=RuntimeError("ingestion blew up"),
        ):
            kb_endpoints._run_kb_update_task(kb_job_id=6, file_paths=["/tmp/d.txt"])
        session.close.assert_called_once()
