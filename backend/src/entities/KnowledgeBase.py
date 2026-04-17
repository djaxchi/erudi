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
        index_path="backend/data/indexes/42.index",
        file_names_list={"file_dropped_paths": ["/uploads/report1.pdf"]}
    )
    kb.add_file_path("/uploads/report2.pdf")
    print(kb.file_count)  # 2
"""
import os
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, JSON
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
        index_path: Filesystem path to FAISS index file (e.g., "backend/data/indexes/42.index").
        created_at: KB creation timestamp.
        file_names_list: JSON dict with source file paths ({"file_dropped_paths": [...]}).
        vectors: Relationship to VectorStore entities (embeddings metadata).
        llm: Relationship to specialized Llm entity (one-to-one).

    Example:
        >>> kb = KnowledgeBase(index_path="backend/data/indexes/15.index")
        >>> kb.file_names_list = {"file_dropped_paths": ["/uploads/doc1.pdf"]}
        >>> kb.add_file_path("/uploads/doc2.pdf")
        >>> print(kb.file_count)  # 2
    """
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    index_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    file_names_list = Column(JSON, nullable=True)

    # Relationships with cascade delete
    vectors = relationship(
        "VectorStore", 
        back_populates="kb", 
        cascade="all, delete-orphan"
    )
    llm = relationship(
        "Llm", 
        back_populates="kb", 
        uselist=False, 
        cascade="all, delete-orphan"
    )

    @property
    def file_paths(self) -> List[str]:
        """Get list of file paths from JSON storage.

        Returns:
            List of file paths or empty list if none stored.
        """
        if not self.file_names_list:
            return []
        return self.file_names_list.get("file_dropped_paths", [])

    @property
    def file_count(self) -> int:
        """Get number of files in KB.

        Returns:
            Count of files stored in file_names_list.
        """
        return len(self.file_paths)

    @property
    def index_exists(self) -> bool:
        """Check if FAISS index file exists on disk.

        Returns:
            True if index_path is set and file exists, False otherwise.
        """
        if not self.index_path:
            return False
        return os.path.exists(self.index_path)

    def add_file_path(self, file_path: str) -> None:
        """Add file path to KB file list.

        Args:
            file_path: Absolute path to file.
        """
        if not self.file_names_list:
            self.file_names_list = {"file_dropped_paths": []}
        
        if "file_dropped_paths" not in self.file_names_list:
            self.file_names_list["file_dropped_paths"] = []
        
        if file_path not in self.file_names_list["file_dropped_paths"]:
            self.file_names_list["file_dropped_paths"].append(file_path)

    def remove_file_path(self, file_path: str) -> bool:
        """Remove file path from KB file list.

        Args:
            file_path: Absolute path to file.

        Returns:
            True if file was removed, False if not found.
        """
        if not self.file_names_list or "file_dropped_paths" not in self.file_names_list:
            return False
        
        try:
            self.file_names_list["file_dropped_paths"].remove(file_path)
            return True
        except ValueError:
            return False

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<KnowledgeBase(id={self.id}, "
            f"files={self.file_count}, "
            f"index={self.index_path})>"
        )