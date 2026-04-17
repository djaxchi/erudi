"""SQLAlchemy entity for fine-tuning job tracking (STUB - not yet implemented).

Tracks background tasks for fine-tuning LLMs with LoRA/QLoRA adapters. Currently
stubbed pending multi-engine training adapter implementation.

Example:
    from src.entities.TrainingJob import TrainingJob

    job = TrainingJob(
        llm_id=42,
        status="pending",
        progress=0.0
    )
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.sql import func
from src.database.core import Base
class TrainingJob(Base):
    """SQLAlchemy model for fine-tuning job tracking (STUB - not implemented).

    Will track background tasks for fine-tuning LLMs with LoRA adapters. Currently
    stubbed pending multi-engine training implementation.

    Attributes:
        id: Primary key (auto-increment).
        llm_id: Foreign key to Llm being trained.
        status: Job state - "pending", "running", "completed", "failed".
        error_message: Exception message if status="failed".
        created_at: Job creation timestamp.
        updated_at: Last status update timestamp.
        progress: Training progress percentage (0.0-100.0).
        time_elapsed: Seconds elapsed since training start.
        time_left: Estimated seconds remaining.

    Example:
        >>> job = TrainingJob(llm_id=42, status="running", progress=50.0)
    """
    __tablename__ = "training_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    llm_id = Column(Integer, ForeignKey("llms.id"))
    status = Column(String, default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    progress = Column(Float, default=0.0)
    time_elapsed = Column(Float, default=0.0)
    time_left = Column(Float, default=0.0)