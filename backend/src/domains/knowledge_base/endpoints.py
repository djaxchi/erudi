"""REST API endpoints for Knowledge Base creation and RAG attachment to LLMs.

Atomic endpoints following REST principles. Each endpoint delegates business
logic to services.

Architecture:
    Endpoints -> Services -> Repository -> Database

Endpoints:
    GET  /knowledge_base/{llm_id}/status - Poll KB job status
    POST /knowledge_base/create - Create new KB assistant or update existing
"""
from typing import List
from fastapi import BackgroundTasks, Depends, APIRouter
from sqlalchemy.orm import Session

from src.database.core import get_db, SessionLocal
from src.domains.knowledge_base.services import KB_Service
from src.domains.knowledge_base.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse
)
from src.core.logging import logger
from src.core.exceptions import (
    AppBaseException,
    KnowledgeBaseNotFoundException,
    DatabaseException,
    InvalidInputException,
)


router = APIRouter(prefix="/knowledge_base", tags=["knowledge_base"])


@router.get("/{llm_id}/status")
def get_kb_job_status(
    llm_id: int,
    db: Session = Depends(get_db)
):
    """Poll Knowledge Base job status with automatic cleanup for failed jobs.

    Args:
        llm_id: Specialized LLM ID created during KB creation.
        db: Database session.

    Returns:
        dict: status, status_updated_at, error_message

    Raises:
        KnowledgeBaseNotFoundException: If KB job not found.
        DatabaseException: If error fetching status.
    """
    service = KB_Service()

    try:
        status_data = service.get_kb_job_status(db, llm_id)
        return status_data

    except ValueError as e:
        logger.error(f"KB job not found: {e}")
        raise KnowledgeBaseNotFoundException(llm_id)

    except Exception as e:
        logger.error(f"Error fetching KB job status: {e}")
        raise DatabaseException(
            "Error fetching KB job status",
            trace=str(e)
        )


@router.post("/create", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create new Knowledge Base assistant or update existing one.

    Decision tree:
    - If base LLM has NO KB attached: Create new specialized LLM + KB
    - If base LLM HAS KB attached: Update existing KB with new documents

    A background task then ingests the documents asynchronously (extraction →
    chunking → embeddings → vector store); the polled status endpoint reports
    progress and errors.

    Args:
        payload: Request body with selectedModel, modelName, description, paths.
        background_tasks: FastAPI background task queue.
        db: Database session.

    Returns:
        KnowledgeBaseResponse: msg and model_id

    Raises:
        InvalidInputException: If validation fails.
        KnowledgeBaseNotFoundException: If base LLM not found.
        DatabaseException: If KB creation fails.
    """
    # Validate payload
    if not payload.paths or not isinstance(payload.paths, list):
        raise InvalidInputException(
            "paths (must be non-empty list)"
        )

    if not payload.selectedModel:
        raise InvalidInputException("selectedModel")

    if not payload.modelName:
        raise InvalidInputException("modelName")

    logger.info(
        f"KB creation request: base_llm={payload.selectedModel}, "
        f"name={payload.modelName}, files={len(payload.paths)}"
    )

    service = KB_Service()

    try:
        # Check if base LLM has existing KB
        from src.domains.knowledge_base.repository import KB_Repository
        repo = KB_Repository()
        base_llm = repo.get_local_llm_by_id(db, payload.selectedModel)

        if not base_llm:
            raise KnowledgeBaseNotFoundException(payload.selectedModel)

        if base_llm.is_attached_to_kb:
            # Update existing KB
            logger.info(f"Updating existing KB for LLM {base_llm.id}")

            llm_id, kb_job_id = service.update_existing_kb(
                db=db,
                base_llm_id=base_llm.id,
                file_paths=payload.paths
            )

            # Queue background task for update
            background_tasks.add_task(
                _run_kb_update_task,
                kb_job_id=kb_job_id,
                file_paths=payload.paths
            )

            return KnowledgeBaseResponse(
                msg="Knowledge Base is being updated with new documents.",
                model_id=llm_id
            )

        else:
            # Create new KB assistant
            logger.info(f"Creating new KB assistant from base LLM {base_llm.id}")

            llm_id, kb_job_id = service.create_kb_assistant(
                db=db,
                base_llm_id=base_llm.id,
                model_name=payload.modelName,
                description=payload.description or "",
                file_paths=payload.paths
            )

            # Queue background task for creation
            background_tasks.add_task(
                _run_kb_creation_task,
                kb_job_id=kb_job_id,
                file_paths=payload.paths
            )

            return KnowledgeBaseResponse(
                msg="Knowledge Base Assistant is being created.",
                model_id=llm_id
            )

    except AppBaseException:
        raise

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise KnowledgeBaseNotFoundException(payload.selectedModel)

    except Exception as e:
        logger.error(f"Error creating KB assistant: {e}")
        raise DatabaseException(
            "Error creating Knowledge Base Assistant",
            trace=str(e)
        )


def _run_kb_creation_task(kb_job_id: int, file_paths: List[str]) -> None:
    """Background task to process documents and create FAISS index.

    Args:
        kb_job_id: KBJob ID to track progress.
        file_paths: List of file paths to process.
    """
    db = SessionLocal()
    service = KB_Service()

    try:
        service.process_and_index_documents(
            db=db,
            kb_job_id=kb_job_id,
            file_paths=file_paths,
            is_update=False
        )
    except Exception as e:
        logger.error(f"KB creation task failed: {e}")
    finally:
        db.close()


def _run_kb_update_task(kb_job_id: int, file_paths: List[str]) -> None:
    """Background task to process new documents and update FAISS index.

    Args:
        kb_job_id: KBJob ID to track progress.
        file_paths: List of new file paths to add.
    """
    db = SessionLocal()
    service = KB_Service()

    try:
        service.process_and_index_documents(
            db=db,
            kb_job_id=kb_job_id,
            file_paths=file_paths,
            is_update=True
        )
    except Exception as e:
        logger.error(f"KB update task failed: {e}")
    finally:
        db.close()
