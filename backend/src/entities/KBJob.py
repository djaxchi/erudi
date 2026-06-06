"""SQLAlchemy entity for Knowledge Base creation/update job tracking.

Tracks background ingestion tasks (extract → chunk → embed → index) during KB
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
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from src.database.core import Base

class KBJobModel(Base):
    """SQLAlchemy model for Knowledge Base creation/update job tracking.

    The id columns are real foreign keys with ON DELETE SET NULL: a job is an
    audit record of its state machine and must survive the deletion of the
    entities it produced (cleanup of a failed creation deletes the specialized
    LLM and the KB — the failed job remains, refs nulled by the server).

    Attributes:
        id: Primary key (auto-increment).
        base_model_id: Base LLM used as foundation (nulled if deleted).
        new_model_id: Specialized LLM created for this KB; equals
            base_model_id for update jobs (nulled if deleted).
        kb_id: KnowledgeBase being created/updated (nulled if deleted).
        status: Job state - "pending", "running", "completed", "failed".
        error_message: Exception message if status="failed".
        created_at: Job creation timestamp (server-stamped).
        updated_at: Last status update timestamp (server-stamped).

    Example:
        >>> job = KBJobModel(base_model_id=42, new_model_id=108, kb_id=15, status="running")
    """
    __tablename__ = "kb_jobs"

    id = Column(Integer, primary_key=True, index=True)
    base_model_id = Column(Integer, ForeignKey("llms.id", ondelete="SET NULL"), nullable=True)
    new_model_id = Column(Integer, ForeignKey("llms.id", ondelete="SET NULL"), nullable=True)
    kb_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="SET NULL"), nullable=True)

    status = Column(String, default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())