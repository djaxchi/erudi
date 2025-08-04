from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, JSON
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class VectorStore(Base):
    __tablename__ = "vector_store"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, unique=True)  # Un seul VectorStore par KB
    vectors_data = Column(JSON, nullable=False)  # JSON: {"faiss_id": "text_content", ...}
    created_at = Column(DateTime, default=datetime.now(), nullable=False)

    # relations
    kb = relationship("KnowledgeBase", back_populates="vectors")