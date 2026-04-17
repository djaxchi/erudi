from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, JSON
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    index_path = Column(String, nullable=False)  # ex. data/indexes/{id}.index
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    file_names_list = Column(JSON, nullable=True)  # Stockage JSON pour la liste de fichiers

    # relations
    vectors = relationship("VectorStore", back_populates="kb", cascade="all, delete-orphan")
    llm = relationship("Llm", back_populates="kb", uselist=False, cascade="all, delete-orphan")