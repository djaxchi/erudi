"""Data access layer for Knowledge Base domain.

Implements repository pattern for database operations related to Knowledge Bases,
VectorStores, LLMs, and KBJobs. All SQL queries isolated here for testability
and separation of concerns.

Classes:
    KB_Repository: Database operations for Knowledge Base entities.

Architecture:
    Endpoints → Services → Repository → Database
    
    This layer handles:
    - CRUD operations on KnowledgeBase, VectorStore, Llm, KBJob
    - Complex queries (joins, filters)
    - Transaction management
    - Database session handling

Examples:
    >>> from src.domains.knowledge_base.repository import KB_Repository
    >>> 
    >>> repo = KB_Repository()
    >>> kb = repo.get_knowledge_base_by_id(db, kb_id=42)
    >>> if kb:
    ...     print(f"KB {kb.id} has {len(kb.file_names_list['file_dropped_paths'])} files")
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.VectorStore import VectorStore
from src.entities.Llm import Llm
from src.entities.KBJob import KBJobModel
from src.core.logging import logger


class KB_Repository:
    """Repository for Knowledge Base domain database operations."""

    # ============ KnowledgeBase Operations ============

    def create_knowledge_base(
        self, 
        db: Session, 
        file_paths: List[str]
    ) -> KnowledgeBase:
        """Create new KnowledgeBase entity.

        Args:
            db: Database session.
            file_paths: List of file paths to store in file_names_list JSON.

        Returns:
            Created KnowledgeBase instance with ID assigned.
        """
        kb = KnowledgeBase(
            file_names_list={"file_dropped_paths": file_paths}
        )
        db.add(kb)
        db.flush()
        logger.info(f"Created KnowledgeBase with ID: {kb.id}")
        return kb

    def get_knowledge_base_by_id(
        self, 
        db: Session, 
        kb_id: int
    ) -> Optional[KnowledgeBase]:
        """Fetch KnowledgeBase by ID.

        Args:
            db: Database session.
            kb_id: KnowledgeBase primary key.

        Returns:
            KnowledgeBase instance or None if not found.
        """
        return db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

    def update_kb_index_path(
        self, 
        db: Session, 
        kb: KnowledgeBase, 
        index_path: str
    ) -> KnowledgeBase:
        """Update KnowledgeBase index_path field.

        Args:
            db: Database session.
            kb: KnowledgeBase instance to update.
            index_path: Filesystem path to FAISS index file.

        Returns:
            Updated KnowledgeBase instance.
        """
        kb.index_path = index_path
        db.commit()
        db.refresh(kb)
        return kb

    def delete_knowledge_base(self, db: Session, kb: KnowledgeBase) -> None:
        """Delete KnowledgeBase (cascades to VectorStore and Llm).

        Args:
            db: Database session.
            kb: KnowledgeBase instance to delete.
        """
        db.delete(kb)
        db.commit()
        logger.info(f"Deleted KnowledgeBase ID: {kb.id}")

    # ============ VectorStore Operations ============

    def create_vector_store(
        self, 
        db: Session, 
        kb_id: int,
        vectors_data: Optional[dict] = None
    ) -> VectorStore:
        """Create VectorStore for a KnowledgeBase.

        Args:
            db: Database session.
            kb_id: Foreign key to KnowledgeBase.
            vectors_data: Optional dict mapping FAISS IDs to text chunks.

        Returns:
            Created VectorStore instance with ID assigned.
        """
        vector_store = VectorStore(
            kb_id=kb_id,
            vectors_data=vectors_data or {}
        )
        db.add(vector_store)
        db.flush()
        logger.info(f"Created VectorStore with ID: {vector_store.id} for KB: {kb_id}")
        return vector_store

    def get_vector_store_by_kb_id(
        self, 
        db: Session, 
        kb_id: int
    ) -> Optional[VectorStore]:
        """Fetch VectorStore by KB ID (unique relationship).

        Args:
            db: Database session.
            kb_id: KnowledgeBase foreign key.

        Returns:
            VectorStore instance or None if not found.
        """
        return db.query(VectorStore).filter(VectorStore.kb_id == kb_id).first()

    def update_vector_store_data(
        self, 
        db: Session, 
        vector_store: VectorStore, 
        vectors_data: dict
    ) -> VectorStore:
        """Update VectorStore vectors_data JSON.

        Args:
            db: Database session.
            vector_store: VectorStore instance to update.
            vectors_data: Dict mapping FAISS IDs (str) to text chunks.

        Returns:
            Updated VectorStore instance.
        """
        vector_store.vectors_data = vectors_data
        db.commit()
        db.refresh(vector_store)
        return vector_store

    def delete_vector_store(self, db: Session, vector_store: VectorStore) -> None:
        """Delete VectorStore.

        Args:
            db: Database session.
            vector_store: VectorStore instance to delete.
        """
        db.delete(vector_store)
        db.commit()
        logger.info(f"Deleted VectorStore ID: {vector_store.id}")

    # ============ Llm Operations ============

    def get_llm_by_id(self, db: Session, llm_id: int) -> Optional[Llm]:
        """Fetch Llm by ID.

        Args:
            db: Database session.
            llm_id: Llm primary key.

        Returns:
            Llm instance or None if not found.
        """
        return db.query(Llm).filter(Llm.id == llm_id).first()

    def get_local_llm_by_id(self, db: Session, llm_id: int) -> Optional[Llm]:
        """Fetch local Llm by ID (local=1 filter).

        Args:
            db: Database session.
            llm_id: Llm primary key.

        Returns:
            Llm instance or None if not found or not local.
        """
        return db.query(Llm).filter(
            Llm.id == llm_id,
            Llm.local == 1
        ).first()

    def create_specialized_llm(
        self,
        db: Session,
        name: str,
        description: str,
        base_llm: Llm,
        kb_id: int
    ) -> Llm:
        """Create specialized LLM attached to Knowledge Base.

        Copies attributes from base LLM and sets is_attached_to_kb=1.

        Args:
            db: Database session.
            name: Name for specialized LLM.
            description: Description for specialized LLM.
            base_llm: Base LLM to copy attributes from.
            kb_id: KnowledgeBase foreign key.

        Returns:
            Created Llm instance with ID assigned.
        """
        specialized_llm = Llm(
            name=name,
            description=description,
            local=1,
            link=base_llm.link,
            type=base_llm.type,
            is_attached_to_kb=1,
            kb_id=kb_id,
            param_size=base_llm.param_size,
            quantized=base_llm.quantized,
        )
        db.add(specialized_llm)
        db.flush()
        logger.info(f"Created specialized Llm with ID: {specialized_llm.id}")
        return specialized_llm

    def delete_llm(self, db: Session, llm: Llm) -> None:
        """Delete Llm.

        Args:
            db: Database session.
            llm: Llm instance to delete.
        """
        db.delete(llm)
        db.commit()
        logger.info(f"Deleted Llm ID: {llm.id}")

    # ============ KBJob Operations ============

    def create_kb_job(
        self,
        db: Session,
        base_model_id: int,
        new_model_id: int,
        kb_id: int,
        status: str = "pending"
    ) -> KBJobModel:
        """Create KBJob to track background task.

        Args:
            db: Database session.
            base_model_id: Base LLM ID.
            new_model_id: Specialized LLM ID (or same as base for updates).
            kb_id: KnowledgeBase ID.
            status: Initial status (default: "pending").

        Returns:
            Created KBJobModel instance with ID assigned.
        """
        kb_job = KBJobModel(
            base_model_id=str(base_model_id),
            new_model_id=str(new_model_id),
            kb_id=str(kb_id),
            status=status
        )
        db.add(kb_job)
        db.flush()
        logger.info(f"Created KBJob with ID: {kb_job.id}")
        return kb_job

    def get_kb_job_by_id(self, db: Session, job_id: int) -> Optional[KBJobModel]:
        """Fetch KBJob by ID.

        Args:
            db: Database session.
            job_id: KBJob primary key.

        Returns:
            KBJobModel instance or None if not found.
        """
        return db.query(KBJobModel).filter(KBJobModel.id == job_id).first()

    def get_kb_job_by_model_id(
        self, 
        db: Session, 
        model_id: int
    ) -> Optional[KBJobModel]:
        """Fetch KBJob by new_model_id (specialized LLM).

        Args:
            db: Database session.
            model_id: Specialized LLM ID (new_model_id).

        Returns:
            KBJobModel instance or None if not found.
        """
        return db.query(KBJobModel).filter(
            KBJobModel.new_model_id == str(model_id)
        ).first()

    def update_kb_job_status(
        self,
        db: Session,
        kb_job: KBJobModel,
        status: str,
        error_message: Optional[str] = None
    ) -> KBJobModel:
        """Update KBJob status and updated_at timestamp.

        Args:
            db: Database session.
            kb_job: KBJobModel instance to update.
            status: New status (pending/running/completed/failed).
            error_message: Optional error message for failed status.

        Returns:
            Updated KBJobModel instance.
        """
        from datetime import datetime
        
        kb_job.status = status
        kb_job.updated_at = datetime.utcnow()
        if error_message:
            kb_job.error_message = error_message
        db.commit()
        db.refresh(kb_job)
        logger.info(f"Updated KBJob {kb_job.id} to status: {status}")
        return kb_job
