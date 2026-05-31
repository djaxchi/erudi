"""Pydantic schemas for conversation and message data validation.

This module defines request/response schemas for:
- Message creation and responses (user/assistant messages)
- Conversation CRUD operations (create, update, read)
- Query parameters for streaming generation
- Bulk operations (delete multiple conversations)
- Message starring (bookmarking)

Schema Hierarchy:
    ::

        MessageBase → MessageCreate, MessageResponse
        ConversationBase → ConversationCreate, ConversationUpdate, ConversationResponse
        ConversationResponse → ConversationWithMessagesResponse

Validation Rules:
    - Message content: 1-32768 characters
    - Message sender: Must be "user" or "assistant"
    - Temperature: 0.0-2.0 (default 0.2)
    - Top-p: 0.0-1.0 (default 0.5)
    - Max tokens: 1-32768 (default 1024)
    - Custom prompt: Max 4096 characters

Example:
    Create conversation request::

        payload = ConversationCreate(
            llm_id=5,
            temperature=0.7,
            top_p=0.9,
            max_tokens=2048,
            custom_prompt="You are a helpful coding assistant."
        )

    Query conversation with message::

        query = ConversationQuery(
            question="Explain asyncio in Python",
            temperature=0.5,
            n_last_turns_to_get=10  # Include last 10 turns in context
        )

Note:
    All schemas use Pydantic v2 field validation with clear error messages.
    from_attributes=True allows ORM model conversion to schema.
"""

"""
Pydantic schemas for conversation-related data validation.
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List, Optional

class MessageBase(BaseModel):
    """Base schema for messages with sender and content validation.

    Attributes:
        sender: Message sender, must be "user" or "assistant".
        content: Message content, 1-32768 characters.
    """
    """Base schema for messages."""
    sender: str = Field(..., description="Message sender (user or assistant)")
    content: str = Field(..., min_length=1, max_length=32768, description="Message content")

    @validator('sender')
    def validate_sender(cls, v):
        """Ensure sender is either 'user', 'assistant', or 'llm'.

        Args:
            v: Sender value to validate.

        Returns:
            str: Validated sender value.

        Raises:
            ValueError: If sender is not "user", "assistant", or "llm".
        """
        if v not in ['user', 'assistant', 'llm']:
            raise ValueError('Sender must be either "user", "assistant", or "llm"')
        return v

class MessageCreate(MessageBase):
    """Schema for creating new messages (inherits all MessageBase fields).

    Example:
        ::

            message = MessageCreate(
                sender="user",
                content="What is the capital of France?"
            )
    """
    """Schema for creating new messages."""
    pass

class MessageResponse(MessageBase):
    """Schema for message responses with database fields.

    Extends MessageBase with id, conversation_id, timestamp, starred.

    Attributes:
        id: Database message ID.
        conversation_id: Parent conversation ID.
        timestamp: Message creation timestamp.
        starred: Whether message is bookmarked (default False).
    """
    """Schema for message responses."""
    id: int = Field(..., description="Message ID")
    conversation_id: int = Field(..., description="Parent conversation ID")
    timestamp: datetime = Field(..., description="Message creation timestamp")
    starred: bool = Field(default=False, description="Whether message is starred")

    class Config:
        from_attributes = True

class ConversationBase(BaseModel):
    """Base schema for conversations with required LLM ID.

    Attributes:
        llm_id: ID of the LLM model to use for this conversation.
    """
    """Base schema for conversations."""
    llm_id: int = Field(..., description="ID of the LLM to use")

class ConversationCreate(ConversationBase):
    """Schema for creating new conversations with generation parameters.

    Attributes:
        llm_id: Inherited from ConversationBase.
        temperature: Sampling temperature (0.0-2.0, default 0.2).
        top_p: Nucleus sampling threshold (0.0-1.0, default 0.5).
        max_tokens: Maximum tokens to generate (1-32768, default 1024).
        custom_prompt: Custom system prompt override (max 4096 chars).

    Example:
        ::

            conv = ConversationCreate(
                llm_id=3,
                temperature=0.8,
                top_p=0.95,
                max_tokens=2048,
                custom_prompt="You are a creative storyteller."
            )
    """
    """Schema for creating new conversations."""
    temperature: Optional[float] = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for text generation"
    )
    top_p: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability threshold"
    )
    max_tokens: Optional[int] = Field(
        default=1024,
        ge=1,
        le=32768,
        description="Maximum number of tokens to generate"
    )
    custom_prompt: Optional[str] = Field(
        default="",
        max_length=4096,
        description="Custom system prompt override"
    )

class ConversationUpdate(ConversationBase):
    """Schema for partial conversation updates (PATCH operations).

    All fields are optional to support partial updates. Only provided
    fields will be updated in the database.

    Attributes:
        llm_id: Optional LLM ID override.
        name: Optional conversation name.
        temperature: Optional temperature override.
        top_p: Optional top_p override.
        max_tokens: Optional max_tokens override.
        custom_prompt: Optional system prompt override.

    Example:
        ::

            update = ConversationUpdate(
                name="Python Best Practices",
                temperature=0.3  # Only update name and temperature
            )
    """
    """Schéma utilisé pour les mises à jour partielles (PATCH)."""

    llm_id: Optional[int] = None
    name: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    custom_prompt: Optional[str] = None

class ConversationResponse(ConversationBase):
    """Schema for conversation responses with full metadata.

    Attributes:
        id: Conversation database ID.
        created_at: Conversation creation timestamp.
        last_message_time: Timestamp of most recent message.
        name: Conversation display name.
        temperature: Current temperature setting.
        top_p: Current top_p setting.
        max_tokens: Current max_tokens setting.
        custom_prompt: Current system prompt.
    """
    id: int
    created_at: datetime
    last_message_time: datetime
    name: str
    temperature: float
    top_p: float
    max_tokens: int
    custom_prompt: str


    class Config:
        from_attributes = True

class ConversationWithMessagesResponse(ConversationResponse):
    """Extended conversation response including full message history.

    Attributes:
        messages: List of all MessageResponse objects in conversation.

    Example:
        ::

            GET /conversations/42
            → ConversationWithMessagesResponse {
                id: 42,
                name: "Python Tutorial",
                messages: [
                  MessageResponse(...),
                  MessageResponse(...)
                ]
              }
    """
    messages: List[MessageResponse]

class ConversationQuery(BaseModel):
    """Schema for querying conversations with streaming generation parameters.

    Attributes:
        question: User message/query to send to LLM.
        temperature: Optional temperature override for this query only.
        top_p: Optional top_p override for this query only.
        max_new_tokens: Optional max_tokens override for this query only.
        custom_prompt: Optional system prompt override for this query only.
        n_last_turns_to_get: Number of recent conversation turns to include.

    Example:
        ::

            query = ConversationQuery(
                question="Explain list comprehensions",
                temperature=0.3,
                n_last_turns_to_get=5  # Include last 5 turns for context
            )
    """
    question: str
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_new_tokens: Optional[int] = None
    custom_prompt: Optional[str] = None
    n_last_turns_to_get: Optional[int] = None

class ConversationDeleteBulk(BaseModel):
    """Schema for bulk conversation deletion requests.

    Attributes:
        conversation_ids: List of conversation IDs to delete.

    Example:
        ::

            DELETE /conversations/delete_bulk
            {
              "conversation_ids": [10, 15, 23, 42]
            }
    """
    conversation_ids: List[int]


class MessageStarRequest(BaseModel):
    """Schema for starring/unstarring messages.

    Attributes:
        message_id: ID of the message to toggle star state.

    Example:
        ::

            POST /conversations/star_message
            {
              "message_id": 345
            }
    """
    message_id: int = Field(..., description="ID of the message to toggle star state")
