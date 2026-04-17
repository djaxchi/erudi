"""SQLAlchemy entity for vector embeddings metadata storage (FAISS ID to text mapping).

Stores the mapping between FAISS vector IDs and their corresponding text chunks for
Knowledge Base retrieval. Each KnowledgeBase has exactly one VectorStore.

Relationships:
    - kb: Many-to-one with KnowledgeBase (parent KB).

Example:
    from src.entities.VectorStore import VectorStore

    vs = VectorStore(
        kb_id=42,
        vectors_data={"0": "First chunk text", "1": "Second chunk text"}
    )
    vs.add_vector(2, "Third chunk text")
    print(vs.vector_count)  # 3
"""
from typing import Optional, Dict
from sqlalchemy import Column, Integer, ForeignKey, DateTime, JSON
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
        vectors_data: JSON dict mapping FAISS IDs to text chunks ({"0": "chunk1", ...}).
        created_at: VectorStore creation timestamp.
        kb: Relationship to KnowledgeBase entity.

    Example:
        >>> vs = VectorStore(kb_id=42, vectors_data={"0": "First chunk", "1": "Second"})
        >>> vs.add_vector(2, "Third chunk")
        >>> print(vs.get_chunk(1))  # "Second"
        >>> print(vs.vector_count)  # 3
    """
    __tablename__ = "vector_store"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(
        Integer, 
        ForeignKey("knowledge_base.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )
    vectors_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    kb = relationship("KnowledgeBase", back_populates="vectors")

    @property
    def vector_count(self) -> int:
        """Get number of vectors stored.

        Returns:
            Count of vectors in vectors_data or 0 if empty.
        """
        if not self.vectors_data:
            return 0
        return len(self.vectors_data)

    def get_chunk(self, faiss_id: int) -> Optional[str]:
        """Get text chunk by FAISS ID.

        Args:
            faiss_id: FAISS vector ID (integer).

        Returns:
            Text chunk string or None if not found.
        """
        if not self.vectors_data:
            return None
        return self.vectors_data.get(str(faiss_id))

    def add_vector(self, faiss_id: int, text_chunk: str) -> None:
        """Add vector mapping to store.

        Args:
            faiss_id: FAISS vector ID (integer).
            text_chunk: Text content for this vector.
        """
        if not self.vectors_data:
            self.vectors_data = {}
        self.vectors_data[str(faiss_id)] = text_chunk

    def remove_vector(self, faiss_id: int) -> bool:
        """Remove vector mapping from store.

        Args:
            faiss_id: FAISS vector ID to remove.

        Returns:
            True if vector was removed, False if not found.
        """
        if not self.vectors_data:
            return False
        
        key = str(faiss_id)
        if key in self.vectors_data:
            del self.vectors_data[key]
            return True
        return False

    def get_all_chunks(self) -> Dict[str, str]:
        """Get all vector mappings.

        Returns:
            Dict mapping FAISS IDs (str) to text chunks, or empty dict.
        """
        return self.vectors_data or {}

    def clear_vectors(self) -> None:
        """Clear all vector mappings."""
        self.vectors_data = {}

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<VectorStore(id={self.id}, "
            f"kb_id={self.kb_id}, "
            f"vectors={self.vector_count})>"
        )