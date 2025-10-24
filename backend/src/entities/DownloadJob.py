"""SQLAlchemy entity for LLM download job tracking with progress and ETA.

Represents a background download task for fetching and quantizing LLMs from HuggingFace.
Tracks progress, timing, file paths, and error states.

Example:
    from src.entities.DownloadJob import DownloadJobModel

    job = DownloadJobModel(
        remote_model_id="meta-llama/Llama-3-8B-Instruct",
        remote_model_link="https://huggingface.co/meta-llama/Llama-3-8B-Instruct",
        local_model_id=42,
        status="pending"
    )
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from src.database.core import Base

class DownloadJobModel(Base):
    """SQLAlchemy model for LLM download jobs with progress tracking and file paths.

    Tracks the lifecycle of downloading and quantizing an LLM from HuggingFace, including
    progress percentage, ETA, temp/final file paths, and error messages.

    Attributes:
        id: Primary key (auto-increment).
        remote_model_id: HuggingFace repo ID (e.g., "meta-llama/Llama-3-8B-Instruct").
        local_model_id: Database ID of temp Llm entry created during download.
        remote_model_link: HuggingFace URL or API endpoint.
        temp_local_model_link: Temp directory for full-precision download.
        final_local_model_link: Final directory for quantized model.
        status: Job state - "pending", "running", "completed", "failed", "cancelled".
        error_message: Exception message if status="failed".
        created_at: Job creation timestamp (server default).
        updated_at: Last status update timestamp (auto-updated).
        total_bytes: Total download size in bytes.
        progress: Download progress percentage (0.0-100.0).
        total_time_elapsed: Seconds elapsed since job start.
        time_left: Estimated seconds remaining.

    Example:
        >>> job = DownloadJobModel(remote_model_id="Qwen/Qwen2.5-7B-Instruct", status="pending")
        >>> job.progress = 50.0
        >>> job.time_left = 120.5
    """
    __tablename__ = "download_jobs"

    id = Column(Integer, primary_key=True, index=True)
    remote_model_id = Column(String, nullable=False)
    local_model_id = Column(String, nullable=True)
    remote_model_link = Column(String, nullable=False)
    temp_local_model_link = Column(String, nullable=True)
    final_local_model_link = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    total_bytes = Column(Float, default=0.0)
    progress = Column(Float, default=0.0)
    total_time_elapsed = Column(Float, default=0.0)
    time_left = Column(Float, default=0.0)
