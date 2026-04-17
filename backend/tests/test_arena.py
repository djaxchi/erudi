"""Comprehensive tests for arena domain (stateless LLM queries).

Tests cover:
- Repository layer (database operations)
- Service layer (business logic with mocked engine)
- Endpoint layer (REST API with streaming)

All LLM_Engine operations are mocked for fast, isolated testing.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import status
from sqlalchemy.orm import Session

from src.domains.arena.repository import ArenaRepository
from src.domains.arena.services import ArenaService
from src.domains.arena.schemas import ArenaQueryPayload
from src.entities.Llm import Llm
from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.VectorStore import VectorStore


# ============ Repository Tests ============

class TestArenaRepository:
    """Test suite for ArenaRepository database operations."""

    def test_get_llm_by_id_success(self, test_db_session, mock_llm):
        """Test successful LLM retrieval by ID.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        repo = ArenaRepository(test_db_session)
        
        llm = repo.get_llm_by_id(mock_llm.id)
        
        assert llm is not None
        assert llm.id == mock_llm.id
        assert llm.name == "Test Base Model"
        assert llm.param_size == 7.0

    def test_get_llm_by_id_not_found(self, test_db_session):
        """Test 404 error when LLM doesn't exist.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = ArenaRepository(test_db_session)
        
        with pytest.raises(Exception) as exc_info:
            repo.get_llm_by_id(999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ============ Service Tests ============

class TestArenaService:
    """Test suite for ArenaService business logic with mocked engine."""

    @pytest.mark.asyncio
    async def test_query_llm_stream_basic(self, test_db_session, mock_llm):
        """Test basic streaming query with mocked engine.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(
            question="What is AI?",
            temperature=0.7,
            top_p=0.9,
            max_new_tokens=512
        )
        
        # Mock engine methods
        mock_model = Mock()
        mock_tokenizer = Mock()
        mock_tokens = ["AI ", "is ", "artificial ", "intelligence."]
        
        with patch("src.core.config.LLM_Engine") as mock_engine:
            mock_engine.get_model_and_tokenizer.return_value = (mock_model, mock_tokenizer)
            mock_engine.generate_stream.return_value = iter(mock_tokens)
            
            # Collect stream output
            result = []
            async for token in service.query_llm_stream(mock_llm.id, payload):
                result.append(token)
        
        assert result == mock_tokens
        assert "".join(result) == "AI is artificial intelligence."
        mock_engine.get_model_and_tokenizer.assert_called_once()
        mock_engine.generate_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_llm_stream_empty_question(self, test_db_session, mock_llm):
        """Test error handling for empty question.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        service = ArenaService(test_db_session)
        
        # Pydantic validation should catch this before service call
        with pytest.raises(Exception):
            payload = ArenaQueryPayload(
                question="",  # Empty string not allowed by Pydantic min_length=1
                temperature=0.5
            )

    @pytest.mark.asyncio
    async def test_query_llm_stream_model_not_found(self, test_db_session):
        """Test error handling when LLM doesn't exist.
        
        Args:
            test_db_session: Database session fixture.
        """
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(question="Test question")
        
        with pytest.raises(Exception) as exc_info:
            async for _ in service.query_llm_stream(999, payload):
                pass
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_query_llm_stream_with_kb(self, test_db_session, mock_llm_with_kb):
        """Test streaming with KB-attached LLM (mocked KB retrieval).
        
        Args:
            test_db_session: Database session fixture.
            mock_llm_with_kb: LLM with KB fixture.
        """
        llm, kb, vector_store = mock_llm_with_kb
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(
            question="What is in the KB?",
            temperature=0.5
        )
        
        mock_model = Mock()
        mock_tokenizer = Mock()
        mock_tokens = ["Answer ", "from ", "KB."]
        
        with patch("src.core.config.LLM_Engine") as mock_engine, \
             patch("src.domains.arena.services.get_relevant_texts_from_kb") as mock_kb:
            
            mock_engine.get_model_and_tokenizer.return_value = (mock_model, mock_tokenizer)
            mock_engine.generate_stream.return_value = iter(mock_tokens)
            mock_kb.return_value = ["Relevant KB context"]
            
            result = []
            async for token in service.query_llm_stream(llm.id, payload):
                result.append(token)
        
        assert result == mock_tokens
        # Verify KB retrieval was called for attached KB
        mock_kb.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_llm_stream_custom_params(self, test_db_session, mock_llm):
        """Test streaming with custom generation parameters.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(
            question="Test custom params",
            temperature=1.5,
            top_p=0.95,
            max_new_tokens=2048,
            custom_prompt="Be concise"
        )
        
        mock_model = Mock()
        mock_tokenizer = Mock()
        mock_tokens = ["Custom ", "response."]
        
        with patch("src.core.config.LLM_Engine") as mock_engine:
            mock_engine.get_model_and_tokenizer.return_value = (mock_model, mock_tokenizer)
            mock_engine.generate_stream.return_value = iter(mock_tokens)
            
            result = []
            async for token in service.query_llm_stream(mock_llm.id, payload):
                result.append(token)
        
        assert result == mock_tokens
        # Verify generate_stream was called with custom params
        call_kwargs = mock_engine.generate_stream.call_args[1]
        assert call_kwargs['temperature'] == 1.5
        assert call_kwargs['top_p'] == 0.95
        assert call_kwargs['max_tokens'] == 2048

    @pytest.mark.asyncio
    async def test_query_llm_stream_engine_failure(self, test_db_session, mock_llm):
        """Test error handling when engine generation fails.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        service = ArenaService(test_db_session)
        payload = ArenaQueryPayload(question="Trigger error")
        
        with patch("src.core.config.LLM_Engine") as mock_engine:
            mock_engine.get_model_and_tokenizer.side_effect = RuntimeError("Model load failed")
            
            with pytest.raises(Exception) as exc_info:
                async for _ in service.query_llm_stream(mock_llm.id, payload):
                    pass
            
            assert "load" in str(exc_info.value).lower()


# ============ Endpoint Tests ============

class TestArenaEndpoints:
    """Test suite for arena REST API endpoints with mocked engine."""

    def test_query_endpoint_success(self, client, test_db_session, mock_llm):
        """Test successful arena query via REST API.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        payload = {
            "question": "What is machine learning?",
            "temperature": 0.7,
            "top_p": 0.9,
            "max_new_tokens": 512
        }
        
        mock_model = Mock()
        mock_tokenizer = Mock()
        mock_tokens = ["Machine ", "learning ", "is ", "AI."]
        
        with patch("src.core.config.LLM_Engine") as mock_engine:
            mock_engine.get_model_and_tokenizer.return_value = (mock_model, mock_tokenizer)
            mock_engine.generate_stream.return_value = iter(mock_tokens)
            
            response = client.post(
                f"/erudi/arena/{mock_llm.id}/query",
                json=payload
            )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.text == "Machine learning is AI."

    def test_query_endpoint_invalid_payload(self, client, test_db_session, mock_llm):
        """Test validation error for invalid payload.
        
        Args:
            client: FastAPI test client.
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        payload = {
            "question": "",  # Empty question - violates min_length=1
            "temperature": 3.0  # Out of range (max 2.0)
        }
        
        response = client.post(
            f"/erudi/arena/{mock_llm.id}/query",
            json=payload
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_endpoint_model_not_found(self, client):
        """Test 404 error when querying non-existent model.
        
        Args:
            client: FastAPI test client.
        """
        payload = {
            "question": "Test question"
        }
        
        response = client.post(
            "/erudi/arena/999/query",
            json=payload
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_query_endpoint_with_custom_prompt(self, client, mock_llm):
        """Test arena query with custom prompt.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        payload = {
            "question": "Explain quantum physics",
            "custom_prompt": "Use simple language for a child",
            "temperature": 0.8
        }
        
        mock_model = Mock()
        mock_tokenizer = Mock()
        mock_tokens = ["Quantum ", "is ", "tiny ", "stuff."]
        
        with patch("src.core.config.LLM_Engine") as mock_engine:
            mock_engine.get_model_and_tokenizer.return_value = (mock_model, mock_tokenizer)
            mock_engine.generate_stream.return_value = iter(mock_tokens)
            
            response = client.post(
                f"/erudi/arena/{mock_llm.id}/query",
                json=payload
            )
        
        assert response.status_code == status.HTTP_200_OK
        assert "Quantum" in response.text
