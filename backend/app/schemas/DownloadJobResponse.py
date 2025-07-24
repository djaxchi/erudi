from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class DownloadJobResponse(BaseModel):
    job_id:             int                = Field(..., alias="id")
    llm_id:             str                = Field(..., alias="model_id")
    model_link:         str
    status:             str
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