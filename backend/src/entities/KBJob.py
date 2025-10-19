from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from src.database.core import Base

class KBJobModel(Base):
    __tablename__ = "kb_jobs"

    id = Column(Integer, primary_key=True, index=True)
    base_model_id = Column(String, nullable=False)
    new_model_id = Column(String, nullable=False)
    kb_id = Column(String, nullable=False)

    status = Column(String, default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())