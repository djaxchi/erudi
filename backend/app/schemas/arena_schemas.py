from pydantic import BaseModel
from typing import Optional

class ArenaQueryPayload(BaseModel):
    question: str       
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_new_tokens: Optional[int] = None 
    custom_prompt: Optional[str] = None
    language: Optional[str] = None       
    n_relevant_msgs_to_get: Optional[int] = None
    n_last_turns_to_get: Optional[int] = None