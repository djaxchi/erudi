from pydantic import BaseModel
from typing import List

class TrainingInfo(BaseModel):
    paths: List[str]
    selectedModel: int
    modelName: str
