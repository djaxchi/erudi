"""
Pydantic schemas for conversation-related data validation.
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List, Optional

class MessageBase(BaseModel):
    """Base schema for messages."""
    sender: str = Field(..., description="Message sender (user or assistant)")
    content: str = Field(..., min_length=1, max_length=32768, description="Message content")

    @validator('sender')
    def validate_sender(cls, v):
        if v not in ['user', 'assistant']:
            raise ValueError('Sender must be either "user" or "assistant"')
        return v

class MessageCreate(MessageBase):
    """Schema for creating new messages."""
    pass

class MessageResponse(MessageBase):
    """Schema for message responses."""
    id: int = Field(..., description="Message ID")
    conversation_id: int = Field(..., description="Parent conversation ID")
    timestamp: datetime = Field(..., description="Message creation timestamp")
    starred: bool = Field(default=False, description="Whether message is starred")

    class Config:
        from_attributes = True

class ConversationBase(BaseModel):
    """Base schema for conversations."""
    llm_id: int = Field(..., description="ID of the LLM to use")

class ConversationCreate(ConversationBase):
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
    """Schéma utilisé pour les mises à jour partielles (PATCH)."""

    llm_id: Optional[int] = None
    name: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    custom_prompt: Optional[str] = None

class ConversationResponse(ConversationBase):
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
    messages: List[MessageResponse]

class ConversationQuery(BaseModel):
    question: str 
    language: Optional[str] = None         
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_new_tokens: Optional[int] = None
    custom_prompt: Optional[str] = None
    n_relevent_msgs_to_get: Optional[int] = None
    n_last_turns_to_get: Optional[int] = None

class ConversationQueryResponse(BaseModel):
    id: int
    link: str
    
    class Config:
        from_attributes = True

class ConversationDeleteBulk(BaseModel):
    conversation_ids: List[int]


class MessageStarRequest(BaseModel):
    message_id: int = Field(..., description="ID of the message to toggle star state")
