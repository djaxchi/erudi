"""Pydantic validation schemas for LLM management and download jobs.

This module defines data transfer objects (DTOs) for the LLMs domain, separating:
- **LLM metadata**: Model catalog entries (name, link, quantization status).
- **Download jobs**: Background tasks for downloading and quantizing models from HuggingFace.

Schema Hierarchy:
- LLMBase → LLMCreate, LLMResponse (inheritance pattern).
- DownloadJobResponse (standalone, aliased fields for API compatibility).

Model State Encoding (local field):
- 0: Remote only (browsable but not downloaded).
- 1: Local (downloaded and ready for inference).
- 2: Downloading (temporary placeholder during download).

Quantization Status (quantized field):
- False: Not quantized (full precision or unknown).
- True: Pre-quantized (model already in 4-bit/8-bit format).

Example:
    from src.domains.llms.schemas import LLMCreate, DownloadJobResponse
    from fastapi import FastAPI

    app = FastAPI()

    @app.post("/llms", response_model=LLMResponse)
    def create_llm(llm: LLMCreate):
        return db.create(llm)
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class LLMBase(BaseModel):
    """Base schema for LLM metadata with minimal required fields.

    Attributes:
        name: Human-readable model name (e.g., "llama-3-8b-instruct").
        local: Download state - 0=remote, 1=local/ready, 2=downloading.
        link: HuggingFace model ID or local filesystem path.
    """
    name: str = Field(..., min_length=1, description="Model name must not be empty")
    local: int = Field(..., ge=0, le=2, description="Must be 0 (remote), 1 (ready), or 2 (downloading)")
    link: str

class LLMCreate(LLMBase):
    """Request schema for creating a new LLM catalog entry.

    Inherits all fields from LLMBase. Used when seeding database from HuggingFace
    or manually registering a model.

    Example:
        >>> llm_data = LLMCreate(name="Qwen2.5-7B", local=0, link="Qwen/Qwen2.5-7B-Instruct")
        >>> response = requests.post("/llms", json=llm_data.model_dump())
    """
    pass

class LLMResponse(LLMBase):
    """Response schema with full LLM metadata including database ID.

    Extends LLMBase with optional fields for detailed model information. Used by
    all read endpoints (list, get, search).

    Attributes:
        id: Database primary key.
        type: Model family (e.g., "llama", "qwen", "mistral").
        description: Model description from HuggingFace or user annotation.
        model_metadata: JSON string with additional metadata (vocab size, context length).
        quantized: Boolean - False=not quantized, True=pre-quantized (already in 4-bit/8-bit format).
        param_size: Model size in billions of parameters (must be positive).
    """
    id: int
    type: Optional[str] = None
    description: Optional[str] = None
    model_metadata: Optional[str] = None
    quantized: Optional[bool] = False
    param_size: Optional[float] = Field(default=4.0, gt=0, description="Parameter size must be positive")

    class Config:
        """Pydantic configuration for LLMResponse model.
        
        Enables ORM mode to directly convert SQLAlchemy Llm entities to Pydantic models.
        """
        from_attributes = True

class DownloadJobResponse(BaseModel):
    """Response schema for download job status with progress tracking.

    Encodes the state of a background download task, including progress metrics,
    file paths, and error information. The job_id field is aliased from 'id' to
    avoid conflicts with LLM IDs in API responses.

    Attributes:
        job_id: Database primary key (aliased from 'id').
        remote_model_id: HuggingFace model ID (e.g., "meta-llama/Llama-3-8B").
        local_model_id: ID of temp LLM entry created during download, -1 on failure.
        remote_model_link: HuggingFace URL or API endpoint.
        local_model_link: Filesystem path to final model after quantization.
        status: Job state - "pending", "running", "completed", "failed", "cancelled".
        total_bytes: Total download size in bytes.
        progress: Download progress percentage (0.0-100.0).
        total_time_elapsed: Seconds elapsed since job start.
        time_left: Estimated seconds remaining (updated each poll).
        error_message: Exception message if status="failed", None otherwise.
        created_at: Job creation timestamp.
        updated_at: Last status update timestamp (used for stale job detection).

    Example:
        >>> job = DownloadJobResponse(
        ...     id=42, remote_model_id="Qwen/Qwen2.5-7B-Instruct", status="running",
        ...     progress=65.0, time_left=120.5, ...
        ... )
        >>> print(job.job_id)  # 42 (aliased from 'id')
    """
    job_id: int = Field(..., alias="id")
    remote_model_id: str = Field(..., min_length=1)
    local_model_id: Optional[int] = None
    remote_model_link: str = Field(..., min_length=1)
    local_model_link: Optional[str] = None
    status: str = Field(..., pattern="^(pending|running|completed|failed|cancelled)$")
    total_bytes: float = Field(default=0.0, ge=0)
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    total_time_elapsed: float = Field(default=0.0, ge=0)
    time_left: float = Field(default=0.0, ge=0)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration for DownloadJobResponse model.
        
        Enables ORM mode and validates field names by alias (job_id aliased from id).
        """
        from_attributes = True
        validate_by_name = True