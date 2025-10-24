
from typing import List

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


def get_conversation_repository(db: Session = Depends(get_db)) -> ConversationRepository:
    """Provide a conversation repository instance."""
    return ConversationRepository(db)


def get_message_repository(db: Session = Depends(get_db)) -> MessageRepository:
    """Provide a message repository instance."""
    return MessageRepository(db)


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
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
    """
    Fetch all messages for a specific conversation.
    """
    return await run_in_threadpool(
        message_repo.get_messages_by_conversation,
        conversation_id,
    )


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    message_repo: MessageRepository = Depends(get_message_repository),
):
    """
    Delete a specific message by its ID.
    """
    await run_in_threadpool(message_repo.delete_message, message_id)
    return {"message": "Message deleted successfully"}


@router.get("/", response_model=List[ConversationResponse])
async def get_all_conversations(
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """
    Fetch all conversations.
    """
    return await run_in_threadpool(conversation_repo.get_all_conversations)


@router.get(
    "/{conversation_id}", response_model=ConversationWithMessagesResponse
)
async def get_conversation_by_id(
    conversation_id: int,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """
    Fetch a single conversation by its ID, including messages.
    """
    return await run_in_threadpool(
        conversation_repo.get_conversation_by_id,
        conversation_id,
    )


@router.post("/", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    service: ConversationService = Depends(get_conversation_service),
):
    """Create a new conversation for a specific LLM (body JSON)."""
    return await run_in_threadpool(
        service.create_conversation,
        payload.llm_id,
        payload.temperature,
        payload.top_p,
        payload.max_tokens,
        payload.custom_prompt,
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Delete a conversation by its ID.
    """
    await run_in_threadpool(service.delete_conversation, conversation_id)
    return {"message": "Conversation deleted successfully"}


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    service: ConversationService = Depends(get_conversation_service),
):
    """Update conversation fields (name and llm_id)."""
    return await run_in_threadpool(
        service.update_conversation,
        conversation_id,
        payload.name,
        payload.llm_id,
        payload.temperature,
        payload.top_p,
        payload.max_tokens,
        payload.custom_prompt,
    )


@router.post("/{conversation_id}/generate_title")
async def generate_title(
    conversation_id: int,
    payload: ConversationQuery,
    service: ConversationService = Depends(get_conversation_service),
):
    """Generate a title for the conversation based on the first message."""
    return StreamingResponse(
        service.generate_title_stream(conversation_id, payload.question),
        media_type="text/plain"
    )


@router.post("/{conversation_id}/query")
async def query_and_respond(
    conversation_id: int,
    payload: ConversationQuery,
    service: ConversationService = Depends(get_conversation_service),
):
    """Query the conversation and get a streaming response."""
    return StreamingResponse(
        service.query_and_respond_stream(conversation_id, payload),
        media_type="text/plain"
    )


@router.post("/delete_bulk")
async def delete_bulk(
    payload: ConversationDeleteBulk,
    service: ConversationService = Depends(get_conversation_service),
):
    """Delete multiple conversations by their IDs (body JSON)."""
    await run_in_threadpool(
        service.delete_conversations_bulk,
        payload.conversation_ids,
    )
    return {"message": "Conversations deleted successfully"}


@router.post("/{conversation_id}/store_error_message")
async def store_error_message(
    conversation_id: int,
    service: ConversationService = Depends(get_conversation_service),
):
    """Store an error message in the conversation when generation fails."""
    error_message_id = await run_in_threadpool(
        service.store_error_message,
        conversation_id,
    )
    return {
        "message": "Error message stored successfully",
        "error_message_id": error_message_id,
    }


@router.post("/star_message")
async def star_message(
    payload: MessageStarRequest,
    message_repo: MessageRepository = Depends(get_message_repository),
):
    """Star a message in the conversation."""
    await run_in_threadpool(message_repo.star_message, payload.message_id)
    return {"state": "success", "message": "Message starred successfully"}


@router.post("/unstar_message")
async def unstar_message(
    payload: MessageStarRequest,
    message_repo: MessageRepository = Depends(get_message_repository),
):
    """Unstar a message in the conversation."""
    await run_in_threadpool(message_repo.unstar_message, payload.message_id)
    return {"state": "success", "message": "Message unstarred successfully"}
