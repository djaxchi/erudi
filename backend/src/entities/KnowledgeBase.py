"""SQLAlchemy entity for Knowledge Base registry.

A KnowledgeBase is the business-level container for a RAG corpus: it owns the
ingested source files (``documents`` → KnowledgeDocument rows) and the
specialized assistant built on top of it (``llm``, one-to-one). The chunks +
embeddings themselves live in the pgvector-managed ``rag.kb_chunks`` table
(langchain-postgres), filtered by ``kb_id`` at retrieval time.

Relationships:
    - documents: One-to-many with KnowledgeDocument (server-side CASCADE).
    - llm: One-to-one with Llm (specialized assistant using this KB).
"""
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.core import Base


class KnowledgeBase(Base):
    """Registry row for one Knowledge Base.

    Attributes:
        id: Primary key (auto-increment).
        created_at: Server-stamped creation timestamp.
        documents: Ingested source files (KnowledgeDocument rows).
        llm: Specialized Llm entity attached to this KB (one-to-one).
    """

    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # ON DELETE CASCADE lives on knowledge_documents.kb_id — passive_deletes
    # lets PostgreSQL do the sweep instead of the ORM loading children.
    documents = relationship(
        "KnowledgeDocument",
        back_populates="kb",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KnowledgeDocument.id",
    )
    llm = relationship(
        "Llm",
        back_populates="kb",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id})>"
