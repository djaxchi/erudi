"""SQLAlchemy entity for Knowledge Base creation job tracking.

Tracks background tasks for embedding documents and building FAISS indexes during KB
assistant creation or update. Monitors status and error messages.

Example:
    from src.entities.KBJob import KBJobModel

    job = KBJobModel(
        base_model_id=42,
        new_model_id=108,
        kb_id=15,
        status="pending"
    )
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from src.database.core import Base

class KBJobModel(Base):
    """SQLAlchemy model for Knowledge Base creation/update job tracking.

    Tracks background tasks for embedding documents and building FAISS indexes. Used
    to monitor progress of KB assistant creation or incremental updates.

    Attributes:
        id: Primary key (auto-increment).
        base_model_id: ID of base LLM used as foundation.
        new_model_id: ID of specialized LLM created for this KB.
        kb_id: ID of KnowledgeBase being created/updated.
        status: Job state - "pending", "running", "completed", "failed".
        error_message: Exception message if status="failed".
        created_at: Job creation timestamp.
        updated_at: Last status update timestamp.

    Example:
        >>> job = KBJobModel(base_model_id=42, new_model_id=108, kb_id=15, status="running")
    """
    __tablename__ = "kb_jobs"

    id = Column(Integer, primary_key=True, index=True)
    base_model_id = Column(String, nullable=False)
    new_model_id = Column(String, nullable=False)
    kb_id = Column(String, nullable=False)

    status = Column(String, default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())