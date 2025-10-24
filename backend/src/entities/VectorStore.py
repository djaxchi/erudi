"""SQLAlchemy entity for vector embeddings metadata storage (FAISS ID to text mapping).

Stores the mapping between FAISS vector IDs and their corresponding text chunks for
Knowledge Base retrieval. Each KnowledgeBase has exactly one VectorStore.

Relationships:
    - kb: Many-to-one with KnowledgeBase (parent KB).

Example:
    from src.entities.VectorStore import VectorStore

    vs = VectorStore(
        kb_id=42,
        vectors_data={"0": "First chunk text", "1": "Second chunk text", ...}
    )
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, JSON
from datetime import datetime
from src.database.core import Base
from sqlalchemy.orm import relationship

class VectorStore(Base):
    """SQLAlchemy model for vector embeddings metadata (FAISS ID → text chunk mapping).

    Stores the mapping between FAISS vector IDs and their source text chunks. Each
    KnowledgeBase has exactly one VectorStore (unique constraint on kb_id).

    Attributes:
        id: Primary key (auto-increment).
        kb_id: Foreign key to KnowledgeBase (unique - one VectorStore per KB).
        vectors_data: JSON dict mapping FAISS IDs to text chunks ({"0": "chunk1", "1": "chunk2", ...}).
        created_at: VectorStore creation timestamp.
        kb: Relationship to KnowledgeBase entity.

    Example:
        >>> vs = VectorStore(kb_id=42, vectors_data={"0": "First chunk", "1": "Second chunk"})
        >>> print(vs.vectors_data["0"])  # "First chunk"
    """
    __tablename__ = "vector_store"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, unique=True)  # Un seul VectorStore par KB
    vectors_data = Column(JSON, nullable=True)  # JSON: {"faiss_id": "text_content", ...}
    created_at = Column(DateTime, default=datetime.now(), nullable=False)

    # relations
    kb = relationship("KnowledgeBase", back_populates="vectors")