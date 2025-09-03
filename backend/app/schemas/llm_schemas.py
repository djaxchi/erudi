from pydantic import BaseModel
from typing import Optional

class LLMBase(BaseModel):
    name: str
    local: int  # 1 for local, 0 for remote
    link: str

class LLMCreate(LLMBase):
    pass

class LLMResponse(LLMBase):
    id: int
    type: Optional[str] = None
    description: Optional[str] = None
    model_metadata: Optional[str] = None

    class Config:
        from_attributes = True