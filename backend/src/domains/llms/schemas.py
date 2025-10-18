from pydantic import BaseModel, Field
from typing import Optional
import datetime

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
    quantized: Optional[int] = 0  # 0 = not quantized, 1 = pre-quantized

    class Config:
        from_attributes = True

class DownloadJobResponse(BaseModel):
    job_id:             int                = Field(..., alias="id")
    remote_model_id:         str
    local_model_id:          Optional[int] = None
    remote_model_link:       str
    local_model_link:        Optional[str] = None
    status:             str  # pending, running, completed, failed
    total_bytes:        float
    progress:           float
    total_time_elapsed: float
    time_left:          float
    error_message:      Optional[str]      = None
    created_at:         datetime
    updated_at:         Optional[datetime] = None

    class Config:
        from_attributes = True
        validate_by_name = True