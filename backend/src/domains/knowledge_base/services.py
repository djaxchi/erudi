"""Business logic layer for Knowledge Base domain.

Implements service pattern for Knowledge Base operations: KB/assistant
lifecycle, job state machine, and background ingestion orchestration.

TRANSITIONAL NOTE (PostgreSQL/pgvector migration): the FAISS ingestion
pipeline (KB_Indexer) died with the VectorStore entity. The new pipeline
(DocumentReader extraction → token-accurate chunking → e5 embeddings →
``langchain_postgres.PGVectorStore``) lands in the ingestion/vector-store
phases of this migration; until then background jobs fail fast with an
explicit message instead of pretending to index.

Classes:
    KB_Service: Business logic for KB creation, updates, and job tracking.

Architecture:
    Endpoints → Services → Repository → Database
"""
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from src.domains.knowledge_base.repository import KB_Repository
from src.entities.KBJob import KBJobModel
from src.core.logging import logger

_PIPELINE_REBUILD_MESSAGE = (
    "KB ingestion pipeline is being rebuilt on PostgreSQL/pgvector — "
    "document indexing is temporarily unavailable."
)


class KB_Service:
    """Business logic for Knowledge Base operations.

    Coordinates KB creation, updates, document processing, and background tasks.
    """

    def __init__(self):
        self.repo = KB_Repository()

    def get_kb_job_status(
        self,
        db: Session,
        llm_id: int
    ) -> Dict[str, Any]:
        """Get KB job status with automatic cleanup for failed jobs.

        Args:
            db: Database session.
            llm_id: Specialized LLM ID (new_model_id in KBJob).

        Returns:
            Dict with status, updated_at, and error_message.

        Raises:
            ValueError: If KB job not found.
        """
        kb_job = self.repo.get_kb_job_by_model_id(db, llm_id)
        if not kb_job:
            raise ValueError(f"KB job not found for LLM ID {llm_id}")

        # Cleanup failed jobs
        if kb_job.status == "failed":
            self._cleanup_failed_job(db, llm_id, kb_job)

        return {
            "status": kb_job.status,
            "status_updated_at": kb_job.updated_at,
            "error_message": kb_job.error_message if kb_job.status == "failed" else None
        }

    def _cleanup_failed_job(
        self,
        db: Session,
        llm_id: int,
        kb_job: KBJobModel
    ) -> None:
        """Clean up database state after a failed KB job.

        Deletes the specialized LLM and its KnowledgeBase; KnowledgeDocument
        rows follow through ON DELETE CASCADE, and the failed job survives as
        an audit record with its refs nulled server-side (FK SET NULL).

        Args:
            db: Database session.
            llm_id: Specialized LLM ID to clean up.
            kb_job: Failed KBJob instance.
        """
        llm = self.repo.get_llm_by_id(db, llm_id)
        if not llm:
            return

        if llm.kb_id:
            kb = self.repo.get_knowledge_base_by_id(db, llm.kb_id)
            if kb:
                self.repo.delete_knowledge_base(db, kb)

        # Delete specialized LLM
        self.repo.delete_llm(db, llm)
        logger.info(f"Cleaned up failed KB job for LLM {llm_id}")

    def create_kb_assistant(
        self,
        db: Session,
        base_llm_id: int,
        model_name: str,
        description: str,
        file_paths: List[str]
    ) -> Tuple[int, int]:  # Returns (llm_id, kb_job_id)
        """Create new Knowledge Base assistant (database setup only).

        Creates specialized LLM, KnowledgeBase, and KBJob entities. Does NOT
        process documents — that's done in the background task.

        Args:
            db: Database session.
            base_llm_id: Base LLM ID to specialize from.
            model_name: Name for specialized assistant.
            description: Description for specialized assistant.
            file_paths: List of file paths to process.

        Returns:
            Tuple of (specialized_llm_id, kb_job_id) for background task.

        Raises:
            ValueError: If base LLM not found or not local.
        """
        # Validate base LLM
        base_llm = self.repo.get_local_llm_by_id(db, base_llm_id)
        if not base_llm:
            raise ValueError(f"Base LLM {base_llm_id} not found or not local")

        # Create Knowledge Base
        kb = self.repo.create_knowledge_base(db)

        # Create specialized LLM
        specialized_llm = self.repo.create_specialized_llm(
            db=db,
            name=model_name,
            description=description,
            base_llm=base_llm,
            kb_id=kb.id
        )

        # Create KBJob
        kb_job = self.repo.create_kb_job(
            db=db,
            base_model_id=base_llm.id,
            new_model_id=specialized_llm.id,
            kb_id=kb.id,
            status="pending"
        )

        db.commit()
        logger.info(
            f"Created KB assistant setup: LLM={specialized_llm.id}, "
            f"KB={kb.id}, Job={kb_job.id}"
        )

        return specialized_llm.id, kb_job.id

    def update_existing_kb(
        self,
        db: Session,
        base_llm_id: int,
        file_paths: List[str]
    ) -> Tuple[int, int]:  # Returns (llm_id, kb_job_id)
        """Queue update for existing KB with new documents (database setup only).

        Creates KBJob for update operation. Does NOT process documents - that's
        done in background task.

        Args:
            db: Database session.
            base_llm_id: Base LLM ID with existing KB attachment.
            file_paths: List of new file paths to add.

        Returns:
            Tuple of (base_llm_id, kb_job_id) for background task.

        Raises:
            ValueError: If LLM not found or KB not attached.
        """
        base_llm = self.repo.get_local_llm_by_id(db, base_llm_id)
        if not base_llm:
            raise ValueError(f"Base LLM {base_llm_id} not found or not local")

        if not base_llm.is_attached_to_kb or not base_llm.kb_id:
            raise ValueError(f"LLM {base_llm_id} is not attached to a KB")

        kb = self.repo.get_knowledge_base_by_id(db, base_llm.kb_id)
        if not kb:
            raise ValueError(f"KB {base_llm.kb_id} not found for LLM {base_llm_id}")

        # Create update job
        kb_job = self.repo.create_kb_job(
            db=db,
            base_model_id=base_llm.id,
            new_model_id=base_llm.id,  # Same LLM for updates
            kb_id=kb.id,
            status="pending"
        )

        db.commit()
        logger.info(f"Created KB update job: Job={kb_job.id}, KB={kb.id}")

        return base_llm.id, kb_job.id

    def process_and_index_documents(
        self,
        db: Session,
        kb_job_id: int,
        file_paths: List[str],
        is_update: bool = False
    ) -> None:
        """Process documents and index them (background task logic).

        TRANSITIONAL: fails the job fast with an explicit message until the
        PGVectorStore ingestion pipeline replaces the FAISS one (see module
        docstring). The polled status endpoint then surfaces the error and
        triggers the standard failed-job cleanup.

        Args:
            db: Database session.
            kb_job_id: KBJob ID to track progress.
            file_paths: List of file paths to process.
            is_update: True if updating existing KB, False if creating new.
        """
        logger.warning(f"KB job {kb_job_id}: {_PIPELINE_REBUILD_MESSAGE}")
        self._handle_indexing_error(db, kb_job_id, _PIPELINE_REBUILD_MESSAGE)

    def _handle_indexing_error(
        self,
        db: Session,
        kb_job_id: int,
        error_message: str
    ) -> None:
        """Handle errors during indexing by marking the job as failed.

        Args:
            db: Database session.
            kb_job_id: KBJob ID that failed.
            error_message: Error description to store.
        """
        try:
            kb_job = self.repo.get_kb_job_by_id(db, kb_job_id)
            if not kb_job:
                return

            # Mark as failed
            self.repo.update_kb_job_status(
                db,
                kb_job,
                "failed",
                error_message=error_message
            )

            # Don't auto-cleanup here - let the status endpoint handle it
            # This way users can see the error message before cleanup

        except Exception as e:
            logger.error(f"Error handling indexing error: {e}")
