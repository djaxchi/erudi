from pydantic import BaseModel
from typing import List

class FolderPaths(BaseModel):
    paths: List[str]
