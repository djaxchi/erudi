"""Comprehensive tests for arena domain (stateless LLM queries).

Tests cover:
- Repository layer (database operations)
- Service layer (business logic with a fake chat model)
- Endpoint layer (REST API with streaming)

Generation goes through the shared AgentRunner (stateless: no checkpointer),
so the fake chat model is injected by patching ``build_chat_model``.
"""

import pytest
from unittest.mock import patch
from fastapi import status

from tests._helpers import ToolableFakeChatModel
from langchain_core.messages import AIMessage

import src.agents.runner as agent_runner
from src.core import config
from src.engines.base_engine import BaseEngine
from src.agents.runner import ERROR_SENTINEL
from src.domains.arena.repository import ArenaRepository
from src.domains.arena.services import ArenaService
from src.domains.arena.schemas import ArenaQueryPayload
from src.utils.kb_utils import KbExcerpt


class _FakeEngine(BaseEngine):
    """Engine stub exposing generation_guard without spawning a real model."""


def _fake_chat_model(*texts):
    """Return a build_chat_model replacement yielding a scripted fake model."""
    msgs = [AIMessage(content=t) for t in texts]
    return lambda llm, **kw: ToolableFakeChatModel(messages=iter(msgs))


# ============ Repository Tests ============

class TestArenaRepository:
    """Test suite for ArenaRepository database operations."""

    def test_get_llm_by_id_success(self, test_db_session, mock_llm):
        repo = ArenaRepository(test_db_session)
        llm = repo.get_llm_by_id(mock_llm.id)
        assert llm is not None
        assert llm.id == mock_llm.id
        assert llm.name == "Test Base Model"
        assert llm.param_size == 7.0

    def test_get_llm_by_id_not_found(self, test_db_session):
        repo = ArenaRepository(test_db_session)
        with pytest.raises(Exception) as exc_info:
            repo.get_llm_by_id(999)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ============ Service Tests ============

class TestArenaService:
    """Test suite for ArenaService business logic (fake chat model)."""

    async def test_query_llm_stream_basic(self, test_db_session, mock_llm, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _fake_chat_model("AI is artificial intelligence."))
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(question="What is AI?", temperature=0.7, top_p=0.9, max_new_tokens=512)

        result = [t async for t in service.query_llm_stream(mock_llm.id, payload)]

        assert "".join(result) == "AI is artificial intelligence."

    async def test_query_llm_stream_empty_question_rejected_by_pydantic(self, test_db_session, mock_llm):
        # Empty question is rejected at the schema level (min_length=1) -> 422.
        with pytest.raises(Exception):
            ArenaQueryPayload(question="", temperature=0.5)

    async def test_query_llm_stream_model_not_found(self, test_db_session):
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(question="Test question")
        with pytest.raises(Exception) as exc_info:
            async for _ in service.query_llm_stream(999, payload):
                pass
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_query_llm_stream_with_kb(self, test_db_session, mock_llm_with_kb, monkeypatch):
        llm, _kb = mock_llm_with_kb
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _fake_chat_model("Answer from KB."))
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(question="What is in the KB?", temperature=0.5)

        with patch("src.domains.arena.services.retrieve_kb_excerpts") as mock_kb:
            mock_kb.return_value = [
                KbExcerpt(source_file="notes.md", text="Relevant KB context")
            ]
            result = [t async for t in service.query_llm_stream(llm.id, payload)]

        assert "".join(result) == "Answer from KB."
        mock_kb.assert_called_once()
        # param_size=7 → medium tier → its KB token budget reaches retrieval.
        assert mock_kb.call_args.kwargs["token_budget"] == 1000

    async def test_query_llm_stream_custom_params(self, test_db_session, mock_llm, monkeypatch):
        # Per-request generation params must reach the model factory.
        captured = {}

        def _capture(llm, **kw):
            captured.update(kw)
            return ToolableFakeChatModel(messages=iter([AIMessage(content="Custom response.")]))

        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _capture)
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(
            question="Test custom params",
            temperature=1.5,
            top_p=0.95,
            max_new_tokens=2048,
            custom_prompt="Be concise",
        )

        result = [t async for t in service.query_llm_stream(mock_llm.id, payload)]

        assert "".join(result) == "Custom response."
        assert captured["temperature"] == 1.5
        assert captured["top_p"] == 0.95
        assert captured["max_tokens"] == 2048

    async def test_query_llm_stream_engine_failure_yields_sentinel(self, test_db_session, mock_llm, monkeypatch):
        # Unified error policy: model-load failure yields the sentinel inline
        # (the old code raised, which was lost after the 200 response started).
        def _boom(llm, **kw):
            raise RuntimeError("Model load failed")

        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _boom)
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(question="Trigger error")

        result = [t async for t in service.query_llm_stream(mock_llm.id, payload)]
        assert any(ERROR_SENTINEL in t for t in result)


# ============ Endpoint Tests ============

class TestArenaEndpoints:
    """Test suite for arena REST API endpoints (fake chat model)."""

    def test_query_endpoint_success(self, client, test_db_session, mock_llm):
        payload = {"question": "What is machine learning?", "temperature": 0.7, "top_p": 0.9, "max_new_tokens": 512}
        with patch.object(agent_runner, "build_chat_model", _fake_chat_model("Machine learning is AI.")):
            response = client.post(f"/erudi/arena/{mock_llm.id}/query", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.text == "Machine learning is AI."

    def test_query_endpoint_invalid_payload(self, client, test_db_session, mock_llm):
        payload = {"question": "", "temperature": 3.0}  # empty + out-of-range
        response = client.post(f"/erudi/arena/{mock_llm.id}/query", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_endpoint_model_not_found(self, client):
        response = client.post("/erudi/arena/999/query", json={"question": "Test question"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_query_endpoint_with_custom_prompt(self, client, mock_llm):
        payload = {"question": "Explain quantum physics", "custom_prompt": "Use simple language for a child", "temperature": 0.8}
        with patch.object(agent_runner, "build_chat_model", _fake_chat_model("Quantum is tiny stuff.")):
            response = client.post(f"/erudi/arena/{mock_llm.id}/query", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert "Quantum" in response.text
