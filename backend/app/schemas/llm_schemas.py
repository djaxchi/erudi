from pydantic import BaseModel

class LLMBase(BaseModel):
    name: str
    local: int  # 1 for local, 0 for remote
    link: str

class LLMCreate(LLMBase):
    pass

class LLMResponse(LLMBase):
    id: int

    class Config:
        from_attributes = True