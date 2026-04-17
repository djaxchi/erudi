from pydantic import BaseModel
from typing import List

class KnowledgeBaseCreate(BaseModel):
    paths: List[str]
    selectedModel: int
    modelName: str
    description: str = None

class KnowledgeBaseResponse(BaseModel):
    model_id: int
    kb_id: int