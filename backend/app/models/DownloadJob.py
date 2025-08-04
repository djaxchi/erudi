from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from app.database import Base

class DownloadJobModel(Base):
    __tablename__ = "download_jobs"

    id = Column(Integer, primary_key=True, index=True)
    remote_model_id = Column(String, nullable=False)
    local_model_id = Column(String, nullable=True)
    remote_model_link = Column(String, nullable=False)
    local_model_link = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    total_bytes = Column(Float, default=0.0)
    progress = Column(Float, default=0.0)
    total_time_elapsed = Column(Float, default=0.0)
    time_left = Column(Float, default=0.0)
