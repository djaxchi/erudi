"""Conversation management API endpoints for chat/streaming functionality.

This module provides REST endpoints for:
- Creating and managing conversations (chat sessions)
- Fetching and deleting messages
- Streaming AI responses with token-by-token generation
- Starring/unstarring messages for bookmarking
- Auto-generating conversation titles
- Bulk operations (delete multiple conversations)

Architecture:
    Conversation Flow:
    ┌────────────────────────────────────────────────────────────┐
    │ POST /conversations/                                       │
    │  └─> Create conversation with LLM + generation params     │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ POST /{conversation_id}/generate_title                     │
    │  └─> Stream AI-generated title based on first message     │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ POST /{conversation_id}/query                              │
    │  └─> Stream AI response token-by-token                    │
    │  └─> Save user message + AI response to database          │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ GET /{conversation_id}/fetch_messages                      │
    │  └─> Retrieve all messages in conversation                │
    └────────────────────────────────────────────────────────────┘

Streaming Pattern:
    All generation endpoints return StreamingResponse with:
    - Content-Type: text/event-stream
    - Token-by-token yields via async generator
    - Automatic database persistence after stream completes

Endpoints:
    - GET / → List all conversations
    - GET /{conversation_id} → Get conversation with messages
    - POST / → Create new conversation
    - PATCH /{conversation_id} → Update conversation (name, LLM, params)
    - DELETE /{conversation_id} → Delete single conversation
    - POST /bulk_delete → Delete multiple conversations
    - POST /{conversation_id}/query → Stream AI response
    - POST /{conversation_id}/generate_title → Stream title generation
    - GET /{conversation_id}/fetch_messages → List messages
    - DELETE /messages/{message_id} → Delete single message
    - PATCH /messages/{message_id}/star → Star/unstar message

Example:
    Create conversation and generate response::

        # 1. Create conversation
        POST /erudi/conversations/
        {
          "llm_id": 1,
          "temperature": 0.7,
          "top_p": 0.9,
          "max_tokens": 512,
          "custom_prompt": "You are a helpful assistant."
        }
        → {"id": 42, "name": "New Conversation", ...}

        # 2. Send message and stream response
        POST /erudi/conversations/42/query
        {
          "user_message": "Explain quantum computing"
        }
        → StreamingResponse (text/event-stream)
        → "Quantum computing..." (token-by-token)

        # 3. Fetch conversation history
        GET /erudi/conversations/42/fetch_messages
        → [
            {"role": "user", "content": "Explain quantum computing"},
            {"role": "assistant", "content": "Quantum computing..."}
          ]

Note:
    - StreamingResponse allows frontend to display tokens in real-time
    - Messages are saved to database only after streaming completes
    - Use run_in_threadpool() for sync repository/service calls

Warning:
    Streaming endpoints hold database sessions during generation.
    Long generations (>60s) may cause connection timeouts.
"""


import asyncio
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, List

from fastapi import Depends, APIRouter
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from src.database.core import get_db
from src.domains.conversations.schemas import (
    ConversationCreate,
    ConversationDeleteBulk,
    ConversationQuery,
    ConversationResponse,
    ConversationUpdate,
    ConversationWithMessagesResponse,
    MessageResponse,
    MessageStarRequest,
)
from src.domains.conversations.repository import ConversationRepository, MessageRepository
from src.domains.conversations.services import ConversationService


router = APIRouter(prefix="/conversations", tags=["conversations"])


def _mlx_thread_initializer() -> None:
    """Warm up MLX GPU streams in the persistent generation thread.

    MLX creates thread-local GPU streams on first use. Running a trivial eval
    here ensures Stream(gpu, 0) exists before any generation call is made,
    which prevents the 'There is no Stream(gpu, 0) in current thread' crash.
    """
    try:
        import mlx.core as mx
        mx.eval(mx.array([1.0]))
    except Exception:
        pass


_MLX_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="mlx-generation",
    initializer=_mlx_thread_initializer,
)


async def _stream_on_single_thread(
    sync_generator_fn, *args, **kwargs
) -> AsyncGenerator[str, None]:
    """Run a sync generator on a persistent single MLX thread and yield its values.

    Uses a single-worker ThreadPoolExecutor so the same OS thread handles every
    generation request. MLX GPU streams are thread-local; initializing them once
    in the executor thread (via _mlx_thread_initializer) and reusing that thread
    avoids the Stream(gpu, 0) crash that occurs when next() is called from an
    arbitrary or freshly-created thread.
    """
    token_queue: queue.Queue = queue.Queue()

    def _run() -> None:
        try:
            for token in sync_generator_fn(*args, **kwargs):
                token_queue.put(token)
        finally:
            token_queue.put(None)  # sentinel

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(_MLX_EXECUTOR, _run)

    while True:
        token = await loop.run_in_executor(None, token_queue.get)
        if token is None:
            break
        yield token

    await future


@router.get("/debug/test_model/{llm_id}")
async def debug_test_model(llm_id: int, db: Session = Depends(get_db)):
    """Temporary debug endpoint to test model loading and generation."""
    import traceback
    from src.core import config
    from src.entities.Llm import Llm
    result = {"steps": []}
    try:
        llm = db.query(Llm).filter(Llm.id == llm_id).first()
        if not llm:
            return {"error": f"LLM {llm_id} not found"}
        result["steps"].append(f"Found LLM: {llm.name}, local={llm.local}, link={llm.link}")

        import os
        link_exists = os.path.exists(llm.link)
        result["steps"].append(f"Path exists: {link_exists}")
        if link_exists:
            contents = os.listdir(llm.link)
            result["steps"].append(f"Path contents: {contents}")

        model, tokenizer = config.LLM_Engine.get_model_and_tokenizer(
            llm_id=llm.id, llm_local_path=llm.link
        )
        result["steps"].append(f"Model loaded: {type(model).__name__}")

        output = ""
        for text in config.LLM_Engine.generate_stream(
            model=model, tokenizer=tokenizer, prompt="Hello",
            max_tokens=5, temperature=1.0, top_p=0.95,
            repetition_penalty=1.2, repetition_context_size=5,
        ):
            output += text
        result["steps"].append(f"Generated: {repr(output)}")
        result["success"] = True
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()
        result["success"] = False
    return result


def get_conversation_repository(db: Session = Depends(get_db)) -> ConversationRepository:
    """Provide a conversation repository instance for dependency injection.

    Args:
        db: SQLAlchemy session injected by FastAPI Depends(get_db).

    Returns:
        ConversationRepository: Repository for conversation CRUD operations.

    Example:
        ::

            @router.get("/")
            async def list_conversations(
                repo: ConversationRepository = Depends(get_conversation_repository)
            ):
                return await run_in_threadpool(repo.get_all_conversations)
    """
    """Provide a conversation repository instance."""
    return ConversationRepository(db)


def get_message_repository(db: Session = Depends(get_db)) -> MessageRepository:
    """Provide a message repository instance for dependency injection.

    Args:
        db: SQLAlchemy session injected by FastAPI Depends(get_db).

    Returns:
        MessageRepository: Repository for message CRUD operations.

    Example:
        ::

            @router.get("/{conversation_id}/messages")
            async def get_messages(
                conversation_id: int,
                repo: MessageRepository = Depends(get_message_repository)
            ):
                return await run_in_threadpool(
                    repo.get_messages_by_conversation, conversation_id
                )
    """
    """Provide a message repository instance."""
    return MessageRepository(db)


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    """Provide a conversation service instance for dependency injection.

    Args:
        db: SQLAlchemy session injected by FastAPI Depends(get_db).

    Returns:
        ConversationService: Service layer for complex conversation operations
            (streaming generation, title generation, message persistence).

    Example:
        ::

            @router.post("/{conversation_id}/query")
            async def query(
                conversation_id: int,
                payload: ConversationQuery,
                service: ConversationService = Depends(get_conversation_service)
            ):
                return StreamingResponse(
                    service.query_conversation(...),
                    media_type="text/event-stream"
                )
    """
    """Provide a conversation service instance."""
    return ConversationService(db)


@router.get(
    "/{conversation_id}/fetch_messages",
    response_model=List[MessageResponse],
)
async def get_messages_by_conversation(
    conversation_id: int,
    message_repo: MessageRepository = Depends(get_message_repository),
):
    """Fetch all messages for a specific conversation ordered by creation time.

    Args:
        conversation_id: ID of the conversation to fetch messages from.
        message_repo: Injected message repository.

    Returns:
        List[MessageResponse]: All messages (user and assistant) in the conversation.

    Example:
        ::

            GET /erudi/conversations/42/fetch_messages
            → [
                {"id": 1, "role": "user", "content": "Hello"},
                {"id": 2, "role": "assistant", "content": "Hi there!"}
              ]
    """
    """
    Fetch all messages for a specific conversation.
    """
    # Read-only operation, no commit needed
    return await run_in_threadpool(
        message_repo.get_messages_by_conversation,
        conversation_id,
    )


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    message_repo: MessageRepository = Depends(get_message_repository),
    db: Session = Depends(get_db),
):
    """Delete a specific message by its ID (soft delete).

    Args:
        message_id: ID of the message to delete.
        message_repo: Injected message repository.
        db: Database session for transaction control.

    Returns:
        dict: Success confirmation message.

    Example:
        ::

            DELETE /erudi/conversations/messages/123
            → {"message": "Message deleted successfully"}
    """
    """
    Delete a specific message by its ID.
    """
    try:
        await run_in_threadpool(message_repo.delete_message, message_id)
        db.commit()
        return {"message": "Message deleted successfully"}
    except Exception:
        db.rollback()
        raise


@router.get("/", response_model=List[ConversationResponse])
async def get_all_conversations(
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """Fetch all conversations from the database.

    Args:
        conversation_repo: Injected conversation repository.

    Returns:
        List[ConversationResponse]: All conversations with metadata (id, name,
            llm_id, creation date, last update).

    Example:
        ::

            GET /erudi/conversations/
            → [
                {
                  "id": 1,
                  "name": "Quantum Computing Discussion",
                  "llm_id": 5,
                  "created_at": "2025-10-24T10:30:00",
                  "temperature": 0.7,
                  "top_p": 0.9
                },
                ...
              ]

    Note:
        Does not include messages. Use GET /{conversation_id} for full details.
    """
    """
    Fetch all conversations.
    """
    # Read-only operation, no commit needed
    return await run_in_threadpool(conversation_repo.get_all_conversations)


@router.get(
    "/{conversation_id}", response_model=ConversationWithMessagesResponse
)
async def get_conversation_by_id(
    conversation_id: int,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """Fetch a single conversation by ID with all associated messages.

    Args:
        conversation_id: ID of the conversation to retrieve.
        conversation_repo: Injected conversation repository.

    Returns:
        ConversationWithMessagesResponse: Conversation metadata and full message
            history (user and assistant messages).

    Example:
        ::

            GET /erudi/conversations/42
            → {
                "id": 42,
                "name": "Python Tutorial",
                "llm_id": 3,
                "messages": [
                  {"role": "user", "content": "Explain decorators"},
                  {"role": "assistant", "content": "Decorators are..."}
                ],
                "temperature": 0.7,
                "custom_prompt": "You are a Python expert."
              }
    """
    """
    Fetch a single conversation by its ID, including messages.
    """
    # Read-only operation, no commit needed
    return await run_in_threadpool(
        conversation_repo.get_conversation_by_id,
        conversation_id,
    )


@router.post("/", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    service: ConversationService = Depends(get_conversation_service),
    db: Session = Depends(get_db),
):
    """Create a new conversation with specified LLM and generation parameters.

    Args:
        payload: ConversationCreate schema with llm_id, temperature, top_p,
            max_tokens, and optional custom_prompt.
        service: Injected conversation service.
        db: Database session for transaction control.

    Returns:
        ConversationResponse: Created conversation with auto-generated name
            (e.g., "New Conversation") and assigned ID.

    Example:
        ::

            POST /erudi/conversations/
            {
              "llm_id": 5,
              "temperature": 0.8,
              "top_p": 0.95,
              "max_tokens": 1024,
              "custom_prompt": "You are a creative writer."
            }
            → {
                "id": 123,
                "name": "New Conversation",
                "llm_id": 5,
                "temperature": 0.8,
                "top_p": 0.95,
                "max_tokens": 1024,
                "custom_prompt": "You are a creative writer."
              }

    Note:
        Use POST /{conversation_id}/generate_title to auto-generate a meaningful
        name after the first message exchange.
    """
    """Create a new conversation for a specific LLM (body JSON)."""
    try:
        conv = await run_in_threadpool(
            service.create_conversation,
            payload.llm_id,
            payload.temperature,
            payload.top_p,
            payload.max_tokens,
            payload.custom_prompt,
        )
        db.commit()
        return conv
    except Exception:
        db.rollback()
        raise


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    service: ConversationService = Depends(get_conversation_service),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all associated messages (cascade delete).

    Args:
        conversation_id: ID of the conversation to delete.
        service: Injected conversation service.
        db: Database session for transaction control.

    Returns:
        dict: Success confirmation message.

    Example:
        ::

            DELETE /erudi/conversations/42
            → {"message": "Conversation deleted successfully"}

    Warning:
        This is a permanent deletion. All messages in the conversation will
        also be deleted due to cascade constraints.
    """
    """
    Delete a conversation by its ID.
    """
    try:
        await run_in_threadpool(service.delete_conversation, conversation_id)
        db.commit()
        return {"message": "Conversation deleted successfully"}
    except Exception:
        db.rollback()
        raise


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    service: ConversationService = Depends(get_conversation_service),
    db: Session = Depends(get_db),
):
    """Update conversation metadata (name, LLM, generation parameters).

    Args:
        conversation_id: ID of the conversation to update.
        payload: ConversationUpdate schema with optional name, llm_id,
            temperature, top_p, max_tokens, custom_prompt.
        service: Injected conversation service.
        db: Database session for transaction control.

    Returns:
        ConversationResponse: Updated conversation with new metadata.

    Example:
        ::

            PATCH /erudi/conversations/42
            {
              "name": "Python Advanced Topics",
              "llm_id": 7,
              "temperature": 0.5,
              "max_tokens": 2048
            }
            → {
                "id": 42,
                "name": "Python Advanced Topics",
                "llm_id": 7,
                "temperature": 0.5,
                "max_tokens": 2048,
                ...
              }

    Note:
        Only provided fields are updated. Omitted fields remain unchanged.
    """
    """Update conversation fields (name and llm_id)."""
    try:
        result = await run_in_threadpool(
            service.update_conversation,
            conversation_id,
            payload.name,
            payload.llm_id,
            payload.temperature,
            payload.top_p,
            payload.max_tokens,
            payload.custom_prompt,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.post("/{conversation_id}/generate_title")
async def generate_title(
    conversation_id: int,
    payload: ConversationQuery,
    service: ConversationService = Depends(get_conversation_service),
):
    """Stream AI-generated conversation title based on first message.

    Uses the loaded LLM to generate a concise title (1-5 words) summarizing
    the conversation topic. Streams title token-by-token for real-time display.

    Args:
        conversation_id: ID of the conversation to generate title for.
        payload: ConversationQuery with question (typically first user message).
        service: Injected conversation service.

    Returns:
        StreamingResponse: Text stream with generated title (text/plain).

    Example:
        ::

            POST /erudi/conversations/42/generate_title
            {
              "question": "Explain quantum entanglement in simple terms"
            }
            → StreamingResponse: "Quantum Entanglement Basics"

    Note:
        Title generation uses the same LLM as the conversation but with
        a specialized prompt: "Generate a 1-5 word title for: {question}"
    """
    """Generate a title for the conversation based on the first message."""
    return StreamingResponse(
        _stream_on_single_thread(
            service.generate_title_stream, conversation_id, payload.question
        ),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{conversation_id}/query")
async def query_and_respond(
    conversation_id: int,
    payload: ConversationQuery,
    service: ConversationService = Depends(get_conversation_service),
):
    """Stream AI response to user query and persist message history.

    This is the core conversation endpoint. It:
    1. Loads conversation history and LLM configuration
    2. Appends user message to history
    3. Streams AI-generated response token-by-token
    4. Saves both user message and AI response to database after streaming

    Args:
        conversation_id: ID of the conversation to query.
        payload: ConversationQuery with user_message and optional kb_id
            (knowledge base for RAG injection).
        service: Injected conversation service.

    Returns:
        StreamingResponse: AI response stream (text/plain), sent token-by-token
            for real-time display in frontend.

    Example:
        ::

            POST /erudi/conversations/42/query
            {
              "user_message": "What is the capital of France?",
              "kb_id": null
            }
            → StreamingResponse: "The capital of France is Paris..."

    Note:
        - Supports RAG: If kb_id provided, injects relevant KB chunks into prompt
        - Messages are saved AFTER streaming completes (ensures full response captured)
        - Uses conversation's temperature, top_p, max_tokens settings
    """
    """Query the conversation and get a streaming response."""
    return StreamingResponse(
        _stream_on_single_thread(
            service.query_and_respond_stream, conversation_id, payload
        ),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/delete_bulk")
async def delete_bulk(
    payload: ConversationDeleteBulk,
    service: ConversationService = Depends(get_conversation_service),
    db: Session = Depends(get_db),
):
    """Delete multiple conversations in a single request (bulk operation).

    Args:
        payload: ConversationDeleteBulk with list of conversation_ids to delete.
        service: Injected conversation service.
        db: Database session for transaction control.

    Returns:
        dict: Success confirmation message.

    Example:
        ::

            POST /erudi/conversations/delete_bulk
            {
              "conversation_ids": [10, 15, 23, 42]
            }
            → {"message": "Conversations deleted successfully"}

    Warning:
        All messages in deleted conversations are also removed (cascade delete).
    """
    """Delete multiple conversations by their IDs (body JSON)."""
    try:
        await run_in_threadpool(
            service.delete_conversations_bulk,
            payload.conversation_ids,
        )
        db.commit()
        return {"message": "Conversations deleted successfully"}
    except Exception:
        db.rollback()
        raise


@router.post("/{conversation_id}/store_error_message")
async def store_error_message(
    conversation_id: int,
    service: ConversationService = Depends(get_conversation_service),
    db: Session = Depends(get_db),
):
    """Store an error message when AI generation fails (fallback mechanism).

    Used by frontend to record generation failures (OOM, timeout, model crash).
    Ensures conversation history remains consistent even after errors.

    Args:
        conversation_id: ID of the conversation where error occurred.
        service: Injected conversation service.
        db: Database session for transaction control.

    Returns:
        dict: ID of the created error message record.

    Example:
        ::

            POST /erudi/conversations/42/store_error_message
            → {"error_message_id": 567}

    Note:
        Error messages are stored with role="assistant" and content indicating
        failure (e.g., "Generation failed due to system error").
    """
    """Store an error message in the conversation when generation fails."""
    try:
        error_message_id = await run_in_threadpool(
            service.store_error_message,
            conversation_id,
        )
        db.commit()
        return {
            "message": "Error message stored successfully",
            "error_message_id": error_message_id,
        }
    except Exception:
        db.rollback()
        raise


@router.post("/star_message")
async def star_message(
    payload: MessageStarRequest,
    message_repo: MessageRepository = Depends(get_message_repository),
    db: Session = Depends(get_db),
):
    """Mark a message as starred (bookmarked for later reference).

    Args:
        payload: MessageStarRequest with message_id to star.
        message_repo: Injected message repository.
        db: Database session for transaction control.

    Returns:
        dict: Success confirmation with state="success".

    Example:
        ::

            POST /erudi/conversations/star_message
            {
              "message_id": 345
            }
            → {"state": "success", "message": "Message starred successfully"}

    Note:
        Starred messages can be filtered/highlighted in frontend for quick access
        to important responses or bookmarked content.
    """
    """Star a message in the conversation."""
    try:
        await run_in_threadpool(message_repo.star_message, payload.message_id)
        db.commit()
        return {"state": "success", "message": "Message starred successfully"}
    except Exception:
        db.rollback()
        raise


@router.post("/unstar_message")
async def unstar_message(
    payload: MessageStarRequest,
    message_repo: MessageRepository = Depends(get_message_repository),
    db: Session = Depends(get_db),
):
    """Remove star/bookmark from a previously starred message.

    Args:
        payload: MessageStarRequest with message_id to unstar.
        message_repo: Injected message repository.
        db: Database session for transaction control.

    Returns:
        dict: Success confirmation with state="success".

    Example:
        ::

            POST /erudi/conversations/unstar_message
            {
              "message_id": 345
            }
            → {"state": "success", "message": "Message unstarred successfully"}
    """
    """Unstar a message in the conversation."""
    try:
        await run_in_threadpool(message_repo.unstar_message, payload.message_id)
        db.commit()
        return {"state": "success", "message": "Message unstarred successfully"}
    except Exception:
        db.rollback()
        raise
