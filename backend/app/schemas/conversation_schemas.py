from pydantic import BaseModel
from datetime import datetime
from typing import List
from ..schemas.message_schemas import MessageResponse

class ConversationBase(BaseModel):
    llm_id: int

class ConversationCreate(ConversationBase):
    pass

class ConversationResponse(ConversationBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class ConversationWithMessagesResponse(ConversationResponse):
    messages: List["MessageResponse"]  # Nested messages