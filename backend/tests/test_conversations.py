"""Comprehensive tests for conversations domain (chat management).

Tests cover:
- Repository layer (conversations and messages CRUD)
- Service layer (chat logic, streaming, title generation with mocked engine)
- Endpoint layer (REST API with streaming responses)

All LLM_Engine operations are mocked for fast, isolated testing.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import status
from sqlalchemy.orm import Session

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

import src.agents.runner as agent_runner
from src.core import config
from src.engines.base_engine import BaseEngine
from src.domains.conversations.repository import ConversationRepository, MessageRepository
from src.domains.conversations.services import ConversationService, _sanitize_title
from src.domains.conversations.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ConversationQuery,
    MessageCreate
)
from src.entities.Conversation import Conversation
from src.entities.Message import Message
from src.entities.Llm import Llm


class _FakeEngine(BaseEngine):
    """Engine stub exposing generation_guard without spawning a real model."""


def _fake_chat_model(*texts):
    """Return a ``build_chat_model`` replacement yielding a scripted fake model.

    ``GenericFakeChatModel`` streams the content word-by-word, so assertions
    compare the concatenated stream (the text/plain wire contract), not the
    original token list.
    """
    msgs = [AIMessage(content=t) for t in texts]
    return lambda llm, **kw: GenericFakeChatModel(messages=iter(msgs))


# ============ Repository Tests ============

class TestConversationRepository:
    """Test suite for ConversationRepository database operations."""

    def test_create_conversation(self, test_db_session, mock_llm):
        """Test conversation creation in database.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        repo = ConversationRepository(test_db_session)
        
        conversation = repo.create_conversation(
            llm_id=mock_llm.id,
            name="Test Chat",
            temperature=0.7,
            top_p=0.9,
            max_tokens=1024
        )
        
        assert conversation.id is not None
        assert conversation.name == "Test Chat"
        assert conversation.llm_id == mock_llm.id
        assert conversation.temperature == 0.7
        assert conversation.top_p == 0.9
        assert conversation.max_tokens == 1024

    def test_get_all_conversations(self, test_db_session, mock_llm):
        """Test retrieving all conversations.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        repo = ConversationRepository(test_db_session)
        
        # Create multiple conversations
        repo.create_conversation(llm_id=mock_llm.id, name="Chat 1", temperature=0.5, top_p=0.8, max_tokens=512)
        repo.create_conversation(llm_id=mock_llm.id, name="Chat 2", temperature=0.7, top_p=0.9, max_tokens=1024)
        
        conversations = repo.get_all_conversations()
        
        assert len(conversations) == 2
        assert conversations[0].name == "Chat 1"
        assert conversations[1].name == "Chat 2"

    def test_get_conversation_by_id(self, test_db_session, mock_llm):
        """Test retrieving specific conversation by ID.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        repo = ConversationRepository(test_db_session)
        
        created = repo.create_conversation(llm_id=mock_llm.id, name="Test", temperature=0.5, top_p=0.8, max_tokens=512)
        retrieved = repo.get_conversation_by_id(created.id)
        
        assert retrieved.id == created.id
        assert retrieved.name == "Test"

    def test_get_conversation_by_id_not_found(self, test_db_session):
        """Test 404 error when conversation doesn't exist.
        
        Args:
            test_db_session: Database session fixture.
        """
        repo = ConversationRepository(test_db_session)
        
        with pytest.raises(Exception) as exc_info:
            repo.get_conversation_by_id(999)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_update_conversation(self, test_db_session, mock_llm):
        """Test updating conversation properties.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        repo = ConversationRepository(test_db_session)
        
        conversation = repo.create_conversation(llm_id=mock_llm.id, name="Original", temperature=0.5, top_p=0.8, max_tokens=512)
        
        updated = repo.update_conversation(
            conversation_id=conversation.id,
            name="Updated",
            temperature=0.9
        )
        
        assert updated.name == "Updated"
        assert updated.temperature == 0.9
        assert updated.top_p == 0.8  # Unchanged

    def test_delete_conversation(self, test_db_session, mock_llm):
        """Test conversation deletion.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        repo = ConversationRepository(test_db_session)
        
        conversation = repo.create_conversation(llm_id=mock_llm.id, name="To Delete", temperature=0.5, top_p=0.8, max_tokens=512)
        
        repo.delete_conversation(conversation.id)
        
        with pytest.raises(Exception):
            repo.get_conversation_by_id(conversation.id)

    def test_delete_conversations_bulk(self, test_db_session, mock_llm):
        """Test bulk conversation deletion.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        repo = ConversationRepository(test_db_session)
        
        c1 = repo.create_conversation(llm_id=mock_llm.id, name="Chat 1", temperature=0.5, top_p=0.8, max_tokens=512)
        c2 = repo.create_conversation(llm_id=mock_llm.id, name="Chat 2", temperature=0.5, top_p=0.8, max_tokens=512)
        c3 = repo.create_conversation(llm_id=mock_llm.id, name="Chat 3", temperature=0.5, top_p=0.8, max_tokens=512)
        
        repo.delete_conversations_bulk([c1.id, c2.id])
        
        remaining = repo.get_all_conversations()
        assert len(remaining) == 1
        assert remaining[0].id == c3.id


class TestMessageRepository:
    """Test suite for MessageRepository database operations."""

    def test_create_message(self, test_db_session, mock_llm):
        """Test message creation in database.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        conv_repo = ConversationRepository(test_db_session)
        msg_repo = MessageRepository(test_db_session)
        
        conversation = conv_repo.create_conversation(llm_id=mock_llm.id, name="Test", temperature=0.5, top_p=0.8, max_tokens=512)
        
        message = msg_repo.create_message(
            conversation_id=conversation.id,
            sender="user",
            content="Hello AI"
        )
        
        assert message.id is not None
        assert message.conversation_id == conversation.id
        assert message.sender == "user"
        assert message.content == "Hello AI"
        assert message.starred == 0

    def test_get_messages_by_conversation_id(self, test_db_session, mock_llm):
        """Test retrieving all messages for a conversation.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        conv_repo = ConversationRepository(test_db_session)
        msg_repo = MessageRepository(test_db_session)
        
        conversation = conv_repo.create_conversation(llm_id=mock_llm.id, name="Test", temperature=0.5, top_p=0.8, max_tokens=512)
        
        msg_repo.create_message(conversation.id, "Question 1", "user")
        msg_repo.create_message(conversation.id, "Answer 1", "llm")
        msg_repo.create_message(conversation.id, "Question 2", "user")
        
        messages = msg_repo.get_messages_by_conversation(conversation.id)
        
        assert len(messages) == 3
        assert messages[0].sender == "user"
        assert messages[1].sender == "llm"
        assert messages[2].content == "Question 2"

    def test_delete_message(self, test_db_session, mock_llm):
        """Test message deletion.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        conv_repo = ConversationRepository(test_db_session)
        msg_repo = MessageRepository(test_db_session)
        
        conversation = conv_repo.create_conversation(llm_id=mock_llm.id, name="Test", temperature=0.5, top_p=0.8, max_tokens=512)
        message = msg_repo.create_message(conversation.id, "To delete", "user")
        
        msg_repo.delete_message(message.id)
        
        messages = msg_repo.get_messages_by_conversation(conversation.id)
        assert len(messages) == 0

    def test_star_message(self, test_db_session, mock_llm):
        """Test starring/bookmarking a message.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        conv_repo = ConversationRepository(test_db_session)
        msg_repo = MessageRepository(test_db_session)
        
        conversation = conv_repo.create_conversation(llm_id=mock_llm.id, name="Test", temperature=0.5, top_p=0.8, max_tokens=512)
        message = msg_repo.create_message(conversation.id, "Important answer", "llm")
        
        msg_repo.star_message(message.id)
        test_db_session.refresh(message)
        
        assert message.starred == 1

    def test_unstar_message(self, test_db_session, mock_llm):
        """Test unstarring a message.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        conv_repo = ConversationRepository(test_db_session)
        msg_repo = MessageRepository(test_db_session)
        
        conversation = conv_repo.create_conversation(llm_id=mock_llm.id, name="Test", temperature=0.5, top_p=0.8, max_tokens=512)
        message = msg_repo.create_message(conversation.id, "Answer", "llm")
        
        # Star then unstar
        msg_repo.star_message(message.id)
        msg_repo.unstar_message(message.id)
        test_db_session.refresh(message)
        
        assert message.starred == 0


# ============ Service Tests ============

class TestConversationService:
    """Test suite for ConversationService business logic with mocked engine."""

    def test_create_conversation_service(self, test_db_session, mock_llm):
        """Test conversation creation via service layer.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        service = ConversationService(test_db_session)
        
        conversation = service.create_conversation(
            llm_id=mock_llm.id,
            temperature=0.6,
            top_p=0.85,
            max_tokens=2048
        )
        
        assert conversation.name  # Auto-generated
        assert conversation.llm_id == mock_llm.id
        assert conversation.llm_id == mock_llm.id

    async def test_delete_conversation_service(self, test_db_session, mock_llm):
        """Test conversation deletion via service (now async; purges checkpointer)."""
        service = ConversationService(test_db_session)

        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.5, top_p=0.8, max_tokens=512)

        await service.delete_conversation(conversation.id)

        # Verify deleted
        with pytest.raises(Exception):
            service.conversation_repo.get_conversation_by_id(conversation.id)

    async def test_delete_conversations_bulk_service(self, test_db_session, mock_llm):
        """Test bulk deletion via service (now async)."""
        service = ConversationService(test_db_session)

        c1 = service.create_conversation(llm_id=mock_llm.id, temperature=0.5, top_p=0.8, max_tokens=512)
        c2 = service.create_conversation(llm_id=mock_llm.id, temperature=0.5, top_p=0.8, max_tokens=512)

        await service.delete_conversations_bulk([c1.id, c2.id])

        remaining = service.conversation_repo.get_all_conversations()
        assert len(remaining) == 0

    def test_store_error_message(self, test_db_session, mock_llm):
        """Test storing error message when generation fails.
        
        Args:
            test_db_session: Database session fixture.
            mock_llm: LLM entity fixture.
        """
        service = ConversationService(test_db_session)
        
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.5, top_p=0.8, max_tokens=512)

        message_id = service.store_error_message(conversation.id)

        assert message_id is not None
        messages = service.message_repo.get_messages_by_conversation(conversation.id)
        assert len(messages) == 1
        assert "[ERROR_MESSAGE_SYSTEM]" in messages[0].content

    async def test_generate_title_stream(self, test_db_session, mock_llm, monkeypatch):
        """Title generation streams via a stateless one-shot model."""
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _fake_chat_model("AI Basics"))
        service = ConversationService(test_db_session)
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.5, top_p=0.8, max_tokens=512)

        result = [t async for t in service.generate_title_stream(conversation.id, "What is AI?")]

        assert "".join(result) == "AI Basics"
        updated_conv = service.conversation_repo.get_conversation_by_id(conversation.id)
        assert updated_conv.name == "AI Basics"

    async def test_generate_title_stream_empty_question(self, test_db_session, mock_llm, monkeypatch):
        """Empty question short-circuits to the default title (no streaming)."""
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        service = ConversationService(test_db_session)
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.5, top_p=0.8, max_tokens=512)

        async for _ in service.generate_title_stream(conversation.id, ""):
            pass

        updated_conv = service.conversation_repo.get_conversation_by_id(conversation.id)
        assert updated_conv.name == "New Conversation"

    async def test_generate_title_sanitizes_junk_to_default(self, test_db_session, mock_llm, monkeypatch):
        """A junk title (markdown fence repetition from a tiny model) is sanitized
        away, so the conversation keeps the default name instead of '```json…'."""
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _fake_chat_model("```json\n```json\n```json"))
        service = ConversationService(test_db_session)
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.5, top_p=0.8, max_tokens=512)

        async for _ in service.generate_title_stream(conversation.id, "Remember this word: SUN. Reply OK."):
            pass

        updated_conv = service.conversation_repo.get_conversation_by_id(conversation.id)
        assert updated_conv.name == "New Conversation"

    async def test_query_and_respond_stream(self, test_db_session, mock_llm, monkeypatch):
        """Query streams the agent response (raw text) and persists both messages."""
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _fake_chat_model("Decorators are functions."))
        service = ConversationService(test_db_session, InMemorySaver())
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.7, top_p=0.9, max_tokens=1024)

        payload = ConversationQuery(
            question="Explain Python decorators",
            temperature=0.7,
            n_last_turns_to_get=5,
        )

        result = [t async for t in service.query_and_respond_stream(conversation.id, payload)]

        assert "".join(result) == "Decorators are functions."

        messages = service.message_repo.get_messages_by_conversation(conversation.id)
        assert len(messages) == 2
        assert messages[0].sender == "user"
        assert messages[0].content == "Explain Python decorators"
        assert messages[1].sender == "llm"
        assert messages[1].content == "Decorators are functions."

    async def test_query_and_respond_stream_with_context(self, test_db_session, mock_llm, monkeypatch):
        """Query with prior messages persists a 4th message (2 prior + user + llm)."""
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _fake_chat_model("Python is versatile."))
        service = ConversationService(test_db_session, InMemorySaver())
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.7, top_p=0.9, max_tokens=1024)

        service.message_repo.create_message(conversation.id, "What is Python?", "user")
        service.message_repo.create_message(conversation.id, "Python is a language.", "llm")

        payload = ConversationQuery(
            question="Tell me more",
            temperature=0.7,
            n_last_turns_to_get=2,
        )

        result = [t async for t in service.query_and_respond_stream(conversation.id, payload)]

        assert "".join(result) == "Python is versatile."

        messages = service.message_repo.get_messages_by_conversation(conversation.id)
        assert len(messages) == 4

    async def test_delete_conversation_purges_checkpointer_thread(self, test_db_session, mock_llm, monkeypatch):
        """IT4 (BLOCKER B3): deleting a conversation purges its checkpointer thread,
        not just the DB rows. SQLite reuses autoincrement ids, so a stale thread
        would otherwise leak a deleted conversation's agent context into a new one.
        """
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
        monkeypatch.setattr(agent_runner, "build_chat_model", _fake_chat_model("An answer."))
        checkpointer = InMemorySaver()
        service = ConversationService(test_db_session, checkpointer)
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.7, top_p=0.9, max_tokens=512)

        payload = ConversationQuery(question="Hello there", temperature=0.7)
        async for _ in service.query_and_respond_stream(conversation.id, payload):
            pass

        cfg = {"configurable": {"thread_id": str(conversation.id)}}
        assert await checkpointer.aget_tuple(cfg) is not None  # thread created by the turn

        await service.delete_conversation(conversation.id)

        assert await checkpointer.aget_tuple(cfg) is None  # B3: thread purged

    async def test_query_failure_persists_sentinel_without_traceback(self, test_db_session, mock_llm, monkeypatch):
        """IT9 (G1): a generation failure persists an llm message carrying the error
        sentinel and NO traceback / internal detail (no info leak), so the UI can
        render an error turn while the user message stays persisted.
        """
        monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)

        def _boom(llm, **kw):
            raise RuntimeError("model load failed: /secret/leak/path")

        monkeypatch.setattr(agent_runner, "build_chat_model", _boom)
        service = ConversationService(test_db_session, InMemorySaver())
        conversation = service.create_conversation(llm_id=mock_llm.id, temperature=0.7, top_p=0.9, max_tokens=512)

        payload = ConversationQuery(question="Trigger failure", temperature=0.7)
        result = [t async for t in service.query_and_respond_stream(conversation.id, payload)]

        assert any("[ERROR_MESSAGE_SYSTEM]" in t for t in result)
        messages = service.message_repo.get_messages_by_conversation(conversation.id)
        # user message persisted up-front + the llm error message
        assert len(messages) == 2
        assert messages[0].sender == "user"
        assert messages[1].sender == "llm"
        assert "[ERROR_MESSAGE_SYSTEM]" in messages[1].content
        assert "Traceback" not in messages[1].content
        assert "/secret/leak/path" not in messages[1].content


# ============ Endpoint Tests ============

class TestConversationEndpoints:
    """Test suite for conversation REST API endpoints with mocked engine."""

    def test_create_conversation_endpoint(self, client, mock_llm):
        """Test conversation creation via REST API.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        payload = {
            "llm_id": mock_llm.id,
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1024
        }
        
        response = client.post("/erudi/conversations/", json=payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Conversation"  # Default name when not specified
        assert data["llm_id"] == mock_llm.id

    def test_get_all_conversations_endpoint(self, client, mock_llm):
        """Test retrieving all conversations via REST API.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        # Create conversations
        client.post("/erudi/conversations/", json={"llm_id": mock_llm.id})
        client.post("/erudi/conversations/", json={"llm_id": mock_llm.id})
        
        response = client.get("/erudi/conversations/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_get_conversation_by_id_endpoint(self, client, mock_llm):
        """Test retrieving specific conversation via REST API.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        create_response = client.post(
            "/erudi/conversations/",
            json={"llm_id": mock_llm.id}
        )
        conversation_id = create_response.json()["id"]
        
        response = client.get(f"/erudi/conversations/{conversation_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == conversation_id
        assert data["name"] == "New Conversation"  # Default name when not specified

    def test_update_conversation_endpoint(self, client, mock_llm):
        """Test updating conversation via REST API.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        create_response = client.post(
            "/erudi/conversations/",
            json={"llm_id": mock_llm.id, "name": "Original"}
        )
        conversation_id = create_response.json()["id"]
        
        update_payload = {"name": "Updated Name", "temperature": 0.9}
        response = client.patch(f"/erudi/conversations/{conversation_id}", json=update_payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["temperature"] == 0.9

    def test_delete_conversation_endpoint(self, client, mock_llm):
        """Test deleting conversation via REST API.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        create_response = client.post(
            "/erudi/conversations/",
            json={"llm_id": mock_llm.id, "name": "To Delete"}
        )
        conversation_id = create_response.json()["id"]
        
        response = client.delete(f"/erudi/conversations/{conversation_id}")
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify deleted
        get_response = client.get(f"/erudi/conversations/{conversation_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_bulk_delete_conversations_endpoint(self, client, mock_llm):
        """Test bulk conversation deletion via REST API.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        c1 = client.post("/erudi/conversations/", json={"llm_id": mock_llm.id}).json()
        c2 = client.post("/erudi/conversations/", json={"llm_id": mock_llm.id}).json()
        
        response = client.post(
            "/erudi/conversations/delete_bulk",
            json={"conversation_ids": [c1["id"], c2["id"]]}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify deleted
        all_response = client.get("/erudi/conversations/")
        assert len(all_response.json()) == 0

    def test_query_endpoint_streaming(self, client, mock_llm):
        """Test streaming query endpoint with mocked engine.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        create_response = client.post(
            "/erudi/conversations/",
            json={"llm_id": mock_llm.id, "name": "Stream Test"}
        )
        conversation_id = create_response.json()["id"]
        
        query_payload = {
            "question": "What is Python?",
            "temperature": 0.7
        }

        # Patch model construction; the client fixture already set a real engine
        # (for generation_guard) and an in-memory checkpointer on app.state.
        with patch.object(agent_runner, "build_chat_model", _fake_chat_model("Python is awesome.")):
            response = client.post(
                f"/erudi/conversations/{conversation_id}/query",
                json=query_payload
            )

        assert response.status_code == status.HTTP_200_OK
        # raw text/plain wire contract: concatenated token text, no SSE framing
        assert response.text == "Python is awesome."

    def test_generate_title_endpoint(self, client, mock_llm):
        """Test title generation endpoint with mocked engine.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
        """
        create_response = client.post(
            "/erudi/conversations/",
            json={"llm_id": mock_llm.id, "name": "New"}
        )
        conversation_id = create_response.json()["id"]
        
        title_payload = {"question": "What is machine learning?"}

        with patch.object(agent_runner, "build_chat_model", _fake_chat_model("ML Intro")):
            response = client.post(
                f"/erudi/conversations/{conversation_id}/generate_title",
                json=title_payload
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.text == "ML Intro"

    def test_get_messages_endpoint(self, client, mock_llm, test_db_session):
        """Test retrieving messages for a conversation.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
            test_db_session: Database session fixture.
        """
        from src.domains.conversations.repository import MessageRepository
        
        create_response = client.post(
            "/erudi/conversations/",
            json={"llm_id": mock_llm.id, "name": "Message Test"}
        )
        conversation_id = create_response.json()["id"]
        
        # Add messages directly
        msg_repo = MessageRepository(test_db_session)
        msg_repo.create_message(conversation_id, "Hello", "user")
        msg_repo.create_message(conversation_id, "Hi there", "llm")
        
        response = client.get(f"/erudi/conversations/{conversation_id}/fetch_messages")
        
        assert response.status_code == status.HTTP_200_OK
        messages = response.json()
        assert len(messages) == 2
        assert messages[0]["content"] == "Hello"
        assert messages[1]["content"] == "Hi there"

    def test_delete_message_endpoint(self, client, mock_llm, test_db_session):
        """Test deleting a message via REST API.
        
        Args:
            client: FastAPI test client.
            mock_llm: LLM entity fixture.
            test_db_session: Database session fixture.
        """
        from src.domains.conversations.repository import ConversationRepository, MessageRepository
        
        conv_repo = ConversationRepository(test_db_session)
        msg_repo = MessageRepository(test_db_session)
        
        conversation = conv_repo.create_conversation(llm_id=mock_llm.id, name="Test", temperature=0.5, top_p=0.8, max_tokens=512)
        message = msg_repo.create_message(conversation.id, "Delete me", "user")
        
        response = client.delete(f"/erudi/conversations/messages/{message.id}")

        assert response.status_code == status.HTTP_200_OK

        # Verify deleted
        messages = msg_repo.get_messages_by_conversation(conversation.id)
        assert len(messages) == 0


# ============ Title sanitization (tiny-model junk titles) ============

class TestTitleSanitization:
    """Unit tests for _sanitize_title (strip markdown noise / repetition / caps)."""

    @pytest.mark.parametrize("raw,expected", [
        ("```json\n```json\n```json\n```json", ""),   # fenced repetition -> empty
        ("Paris, City of Light", "Paris, City of Light"),
        ('"Pizza Recipe"', "Pizza Recipe"),            # wrapping quotes stripped
        ("json json json", ""),                         # dedupe -> 'json' -> rejected
        ("# Google Founding Team", "Google Founding Team"),  # heading marker stripped
        ("```\ntext\n```", ""),                         # fence + generic noise -> empty
        ("", ""),
    ])
    def test_sanitize_title(self, raw, expected):
        assert _sanitize_title(raw) == expected

    def test_sanitize_title_caps_word_count(self):
        assert _sanitize_title("one two three four five six seven eight") == "one two three four five six"
