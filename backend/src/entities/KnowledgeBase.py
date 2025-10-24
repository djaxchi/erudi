"""SQLAlchemy entity for Knowledge Base metadata and FAISS index tracking.

Represents a Knowledge Base with FAISS vector index, source file tracking, and
relationships to VectorStore and specialized LLM. Used for RAG (Retrieval-Augmented
Generation) workflows.

Relationships:
    - vectors: One-to-many with VectorStore (vector embeddings metadata).
    - llm: One-to-one with Llm (specialized assistant using this KB).

Example:
    from src.entities.KnowledgeBase import KnowledgeBase

    kb = KnowledgeBase(
        index_path="/data/indexes/42.index",
        file_names_list={"file_dropped_paths": ["/uploads/report1.pdf", "/uploads/report2.pdf"]}
    )
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, JSON
from datetime import datetime
from src.database.core import Base
from sqlalchemy.orm import relationship

class KnowledgeBase(Base):
    """SQLAlchemy model for Knowledge Base with FAISS index and file tracking.

    Stores metadata for a Knowledge Base including FAISS index path, source files,
    and creation timestamp. Links to VectorStore for embeddings and Llm for the
    specialized assistant.

    Attributes:
        id: Primary key (auto-increment).
        index_path: Filesystem path to FAISS index file (e.g., "data/indexes/42.index").
        created_at: KB creation timestamp.
        file_names_list: JSON dict with source file paths ({"file_dropped_paths": [...]}).
        vectors: Relationship to VectorStore entities (embeddings metadata).
        llm: Relationship to specialized Llm entity (one-to-one).

    Example:
        >>> kb = KnowledgeBase(index_path="/data/indexes/15.index")
        >>> kb.file_names_list = {"file_dropped_paths": ["/uploads/doc1.pdf"]}
    """
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    index_path = Column(String, nullable=True)  # ex. data/indexes/{id}.index
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    file_names_list = Column(JSON, nullable=True)  # Stockage JSON pour la liste de fichiers

    # relations
    vectors = relationship("VectorStore", back_populates="kb", cascade="all, delete-orphan")
    llm = relationship("Llm", back_populates="kb", uselist=False, cascade="all, delete-orphan")