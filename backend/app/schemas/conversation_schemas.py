from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from ..schemas.message_schemas import MessageResponse

class ConversationBase(BaseModel):
    llm_id: int

class ConversationCreate(ConversationBase):
    pass

class ConversationUpdate(ConversationBase):
    """Schéma utilisé pour les mises à jour partielles (PATCH)."""

    llm_id: Optional[int] = None
    name: Optional[str] = None

class ConversationResponse(ConversationBase):
    id: int
    created_at: datetime
    last_message_time: datetime
    name: str


    class Config:
        from_attributes = True

class ConversationWithMessagesResponse(ConversationResponse):
    messages: List[MessageResponse]

class ConversationQuery(BaseModel):
    question: str
    history: Optional[List[dict]] = None    
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