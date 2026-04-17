"""Business logic layer for Knowledge Base domain.

Implements service pattern for Knowledge Base operations including document
ingestion, FAISS indexing, and background task orchestration. Services
coordinate between repositories, utils, and engines.

Classes:
    KB_Service: Business logic for KB creation, updates, and RAG operations.
    KB_Indexer: FAISS index management and embedding operations.

Architecture:
    Endpoints → Services → Repository → Database
                     ↓
                  Utils/Engines

Examples:
    >>> from src.domains.knowledge_base.services import KB_Service
    >>> from src.database.core import get_db
    >>> 
    >>> service = KB_Service()
    >>> db = next(get_db())
    >>> result = service.create_kb_assistant(
    ...     db=db,
    ...     base_llm_id=42,
    ...     model_name="Finance Assistant",
    ...     description="Q1-Q4 2024",
    ...     file_paths=["/uploads/q1.pdf"]
    ... )
"""
import os
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime

import faiss
import numpy

from sqlalchemy.orm import Session

from src.domains.knowledge_base.repository import KB_Repository
from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.VectorStore import VectorStore
from src.entities.Llm import Llm
from src.entities.KBJob import KBJobModel

from src.engines.embedder_engine import Embedder_Engine
from src.utils.file_processor import prepare_for_knowledge_base, chunk_by_tokens
from src.core.config import INDEXES_DIR
from src.core.logging import logger
from src.core.exceptions import (
    FAISSException,
    EmbeddingError,
    FileSystemException,
    KnowledgeBaseNotFoundException,
    KnowledgeBaseCorruptedException,
    DatabaseException,
)


class KB_Indexer:
    """FAISS index management and text embedding operations.
    
    Handles low-level FAISS operations including index creation, population,
    and persistence. Separates indexing logic from business logic.
    """

    @staticmethod
    def create_faiss_index(dimension: int = 384) -> Any:
        """Create new FAISS IndexIDMap with L2 distance.

        Args:
            dimension: Vector dimension (default: 384 for MiniLM).

        Returns:
            FAISS IndexIDMap wrapping IndexFlatL2.
        """
        base_index = faiss.IndexFlatL2(dimension)
        index = faiss.IndexIDMap(base_index)
        logger.info(f"Created FAISS index with dimension: {dimension}")
        return index

    @staticmethod
    def embed_and_index_texts(
        texts: List[str],
        index: Any,
        vectors_data: Dict[str, str],
        start_id: int = 0
    ) -> Tuple[Any, Dict[str, str], int]:
        """Embed texts and add to FAISS index with sequential IDs.

        Chunks each text, embeds chunks via Embedder_Engine, and adds to
        FAISS index with custom integer IDs.

        Args:
            texts: Full-text documents to process.
            index: FAISS IndexIDMap to populate.
            vectors_data: Dict mapping FAISS ID (str) to chunk text.
            start_id: Starting FAISS ID (0 for new, max+1 for updates).

        Returns:
            Tuple of (updated index, updated vectors_data, next_available_id).
        """
        embedder = Embedder_Engine.get_embedder()
        current_id = start_id

        for text_idx, text in enumerate(texts):
            if not text.strip():
                continue

            logger.info(f"Processing text {text_idx + 1}/{len(texts)}: {len(text)} chars")
            chunks = chunk_by_tokens(text=text)
            
            if not chunks:
                logger.warning(f"No chunks created for text {text_idx + 1}")
                continue

            logger.info(f"Created {len(chunks)} chunks for text {text_idx + 1}")

            for chunk_idx, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                try:
                    # Embed chunk
                    embedding = embedder.encode(
                        chunk, 
                        show_progress_bar=False, 
                        convert_to_tensor=True
                    )

                    if embedding is None or embedding.numel() == 0:
                        logger.error(f"Empty embedding for chunk {chunk_idx + 1}")
                        continue

                    # Convert to numpy float32 for FAISS
                    emb_numpy = embedding.detach().cpu().numpy().astype("float32").reshape(1, -1)

                    # Add to FAISS with custom ID
                    index.add_with_ids(emb_numpy, numpy.array([current_id]))

                    # Store text mapping
                    vectors_data[str(current_id)] = chunk

                    logger.debug(f"Indexed chunk {current_id}: {chunk[:50]}...")
                    current_id += 1

                except EmbeddingError:
                    raise
                except Exception as e:
                    logger.error(f"Error indexing chunk {chunk_idx + 1}: {e}")
                    raise EmbeddingError(
                        f"Failed to embed chunk {chunk_idx + 1}",
                        trace=str(e)
                    )

        Embedder_Engine.cleanup()
        logger.info(f"Indexed {current_id - start_id} vectors (IDs {start_id} to {current_id - 1})")
        
        return index, vectors_data, current_id

    @staticmethod
    def save_index(index: Any, file_path: str) -> None:
        """Write FAISS index to disk.

        Args:
            index: FAISS index to persist.
            file_path: Absolute path for index file.

        Raises:
            RuntimeError: If write operation fails.
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            faiss.write_index(index, file_path)
            logger.info(f"Saved FAISS index to {file_path}")
        except OSError as e:
            logger.error(f"Filesystem error saving FAISS index: {e}")
            raise FileSystemException(
                f"Failed to save FAISS index to {file_path}",
                trace=str(e)
            )
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            raise FAISSException(
                f"FAISS write operation failed: {e}",
                trace=str(e)
            )

    @staticmethod
    def load_index(file_path: str) -> Any:
        """Load FAISS index from disk.

        Args:
            file_path: Absolute path to index file.

        Returns:
            Loaded FAISS index.

        Raises:
            FileNotFoundError: If index file doesn't exist.
            RuntimeError: If read operation fails.
        """
        if not os.path.exists(file_path):
            raise FileSystemException(f"FAISS index not found at {file_path}")

        try:
            index = faiss.read_index(file_path)
            logger.info(f"Loaded FAISS index from {file_path} ({index.ntotal} vectors)")
            return index
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            raise FAISSException(
                f"FAISS read operation failed: {e}",
                trace=str(e)
            )

    @staticmethod
    def verify_index(file_path: str) -> bool:
        """Verify FAISS index readability and perform test search.

        Args:
            file_path: Path to index file.

        Returns:
            True if index is valid and searchable, False otherwise.
        """
        try:
            index = KB_Indexer.load_index(file_path)
            
            if index.ntotal == 0:
                logger.warning("Index is empty")
                return True  # Empty but valid

            # Test search with dummy query
            embedder = Embedder_Engine.get_embedder()
            query_emb = embedder.encode("test query", convert_to_tensor=True)
            q = numpy.ascontiguousarray(
                query_emb.detach().cpu().numpy().astype("float32")
            ).reshape(1, -1)
            
            _, indices = index.search(q, k=1)
            logger.info(f"Index verification successful: found ID {indices[0][0]}")
            Embedder_Engine.cleanup()
            return True

        except Exception as e:
            logger.error(f"Index verification failed: {e}")
            return False


class KB_Service:
    """Business logic for Knowledge Base operations.
    
    Coordinates KB creation, updates, document processing, and background tasks.
    """

    def __init__(self):
        self.repo = KB_Repository()
        self.indexer = KB_Indexer()

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
        """Clean up database and filesystem after failed KB job.

        Deletes LLM, VectorStore, KnowledgeBase, and FAISS index file.

        Args:
            db: Database session.
            llm_id: Specialized LLM ID to clean up.
            kb_job: Failed KBJob instance.
        """
        llm = self.repo.get_llm_by_id(db, llm_id)
        if not llm:
            return

        if llm.kb_id:
            # Delete VectorStore
            vector_store = self.repo.get_vector_store_by_kb_id(db, llm.kb_id)
            if vector_store:
                self.repo.delete_vector_store(db, vector_store)

            # Delete KB and index file
            kb = self.repo.get_knowledge_base_by_id(db, llm.kb_id)
            if kb:
                if kb.index_path and os.path.exists(kb.index_path):
                    try:
                        os.remove(kb.index_path)
                        logger.info(f"Removed failed index file: {kb.index_path}")
                    except Exception as e:
                        logger.error(f"Failed to remove index file: {e}")
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

        Creates specialized LLM, KnowledgeBase, VectorStore, and KBJob entities.
        Does NOT process documents or build index - that's done in background task.

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
        kb = self.repo.create_knowledge_base(db, file_paths)

        # Create specialized LLM
        specialized_llm = self.repo.create_specialized_llm(
            db=db,
            name=model_name,
            description=description,
            base_llm=base_llm,
            kb_id=kb.id
        )

        # Create VectorStore
        vector_store = self.repo.create_vector_store(db, kb.id)

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
        """Process documents and build/update FAISS index (background task logic).

        Complete pipeline: prepare files → embed chunks → index → persist.

        Args:
            db: Database session.
            kb_job_id: KBJob ID to track progress.
            file_paths: List of file paths to process.
            is_update: True if updating existing KB, False if creating new.

        Raises:
            Exception: Any error during processing (logged and stored in KBJob).
        """
        try:
            # Mark job as running
            kb_job = self.repo.get_kb_job_by_id(db, kb_job_id)
            if not kb_job:
                raise ValueError(f"KBJob {kb_job_id} not found")

            self.repo.update_kb_job_status(db, kb_job, "running")

            # Get entities
            kb = self.repo.get_knowledge_base_by_id(db, kb_job.kb_id)
            if not kb:
                raise ValueError(f"KnowledgeBase {kb_job.kb_id} not found")

            vector_store = self.repo.get_vector_store_by_kb_id(db, kb_job.kb_id)
            if not vector_store:
                raise ValueError(f"VectorStore not found for KB {kb_job.kb_id}")

            # Prepare documents
            logger.info(f"Preparing {len(file_paths)} files for KB {kb.id}")
            texts = prepare_for_knowledge_base(file_paths)
            if not texts:
                raise ValueError("No valid texts extracted from files")

            logger.info(f"Extracted {len(texts)} texts from files")

            # Build or update index
            if is_update:
                self._update_index(db, kb, vector_store, texts)
            else:
                self._create_index(db, kb, vector_store, texts)

            # Verify index
            if not self.indexer.verify_index(kb.index_path):
                raise RuntimeError("Index verification failed")

            # Mark job as completed
            self.repo.update_kb_job_status(db, kb_job, "completed")
            logger.info(f"KB job {kb_job_id} completed successfully")

        except Exception as e:
            logger.error(f"Error in KB job {kb_job_id}: {e}")
            self._handle_indexing_error(db, kb_job_id, str(e))
            raise

    def _create_index(
        self,
        db: Session,
        kb: KnowledgeBase,
        vector_store: VectorStore,
        texts: List[str]
    ) -> None:
        """Create new FAISS index from scratch.

        Args:
            db: Database session.
            kb: KnowledgeBase instance.
            vector_store: VectorStore instance.
            texts: Document texts to index.
        """
        # Create FAISS index
        index = self.indexer.create_faiss_index()

        # Embed and index texts
        vectors_data = {}
        index, vectors_data, _ = self.indexer.embed_and_index_texts(
            texts=texts,
            index=index,
            vectors_data=vectors_data,
            start_id=0
        )

        logger.info(f"Indexed {len(vectors_data)} chunks for KB {kb.id}")

        # Save index to disk
        index_path = INDEXES_DIR / f"{kb.id}.index"
        self.indexer.save_index(index, str(index_path))

        # Update database
        self.repo.update_kb_index_path(db, kb, str(index_path))
        self.repo.update_vector_store_data(db, vector_store, vectors_data)

    def _update_index(
        self,
        db: Session,
        kb: KnowledgeBase,
        vector_store: VectorStore,
        texts: List[str]
    ) -> None:
        """Update existing FAISS index with new documents.

        Args:
            db: Database session.
            kb: KnowledgeBase instance.
            vector_store: VectorStore instance.
            texts: New document texts to add.
        """
        # Load existing index
        index = self.indexer.load_index(kb.index_path)
        vectors_data = vector_store.vectors_data.copy()

        # Get next available ID
        start_id = max(int(k) for k in vectors_data.keys()) + 1 if vectors_data else 0

        # Add new vectors
        index, vectors_data, _ = self.indexer.embed_and_index_texts(
            texts=texts,
            index=index,
            vectors_data=vectors_data,
            start_id=start_id
        )

        logger.info(f"Added new chunks to KB {kb.id} (now {len(vectors_data)} total)")

        # Save updated index
        self.indexer.save_index(index, kb.index_path)

        # Update database
        self.repo.update_vector_store_data(db, vector_store, vectors_data)

    def _handle_indexing_error(
        self,
        db: Session,
        kb_job_id: int,
        error_message: str
    ) -> None:
        """Handle errors during indexing by cleaning up and marking job as failed.

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
