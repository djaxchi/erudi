from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

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