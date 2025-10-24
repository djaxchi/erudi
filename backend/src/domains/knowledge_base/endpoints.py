"""REST API endpoints for Knowledge Base (KB) creation and RAG attachment to LLMs.

This module orchestrates the complete lifecycle of Knowledge Base assistants:
1. **Document ingestion**: Parse PDFs/TXT files → chunk by tokens.
2. **Vector indexing**: Embed chunks via sentence-transformers → FAISS IndexIDMap.
3. **LLM specialization**: Create specialized LLM entry attached to KB (kb_id FK).
4. **Background processing**: Queue KB jobs for async embedding + indexing.

Architecture:
    ┌──────────────┐
    │ User uploads │
    │ PDF/TXT files│
    └───────┬──────┘
            │ (1) create_knowledge_base() → validates files
            ↓
    ┌──────────────┐
    │ Prepare docs │ ← file_processor.prepare_for_knowledge_base()
    │ & chunk text │ ← file_processor.chunk_by_tokens(chunk_size=512)
    └───────┬──────┘
            │ (2) Create KnowledgeBase + VectorStore + specialized Llm
            ↓
    ┌──────────────┐
    │ Background   │ ← BackgroundTasks.add_task(init_new_kb_assistant)
    │ FAISS index  │   or update_kb_assistant_with_new_data()
    └───────┬──────┘
            │ (3) Embed chunks via sentence-transformers
            │ (4) Store in FAISS IndexIDMap (384-dim float32)
            ↓
    ┌──────────────┐
    │ Ready for    │ ← RAG queries use faiss.search(k=5)
    │ inference    │   inject top-5 chunks into prompt context
    └──────────────┘

Data Model:
    - **KnowledgeBase**: Stores file_names_list JSON + index_path on disk.
    - **VectorStore**: Stores vectors_data JSON mapping FAISS IDs → text chunks.
    - **Llm**: Specialized model entry with is_attached_to_kb=1 + kb_id FK.
    - **KBJob**: Background task status (pending/running/completed/failed).

FAISS Configuration:
    - IndexFlatL2(384): Brute-force L2 distance (exact search).
    - IndexIDMap: Wraps IndexFlatL2 to allow custom integer IDs per chunk.
    - Vectors stored as float32 numpy arrays (CPU-based, no GPU required).

Endpoints:
    - GET  /knowledge_base/{llm_id}/status → Poll KB job progress.
    - POST /knowledge_base/create → Create new KB assistant or update existing.

Background Tasks:
    - init_new_kb_assistant(): First-time setup (create index, embed all chunks).
    - update_kb_assistant_with_new_data(): Incremental update (add new chunks to existing index).
    - populate_vector_store(): Shared embedding logic for both tasks.

Error Handling:
    - Failed jobs clean up temp LLM entries, VectorStore, and FAISS index files.
    - Status polling returns error_message when status="failed".

Example:
    POST /knowledge_base/create
    {
        "selectedModel": 42,
        "modelName": "Financial Reports Assistant",
        "description": "Specialized for Q1-Q4 2024 earnings reports",
        "paths": ["/uploads/q1_2024.pdf", "/uploads/q2_2024.pdf"]
    }
    Response: {"msg": "Knowledge Base Assistant is being created.", "model_id": 108}

    GET /knowledge_base/108/status
    Response: {"status": "running", "status_updated_at": "2024-01-15T10:30:00Z"}
"""
import os
# os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1") # Accelerate/vecLib (macOS)
# os.environ.setdefault("OMP_NUM_THREADS", "1")
# os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
# os.environ.setdefault("MKL_NUM_THREADS", "1")
# os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
import faiss, numpy
# faiss.omp_set_num_threads(1)
from datetime import datetime
from typing import Any, List

from fastapi import BackgroundTasks, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from src.database.core import get_db, SessionLocal

from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.VectorStore import VectorStore
from src.entities.Llm import Llm
from src.entities.KBJob import KBJobModel

from src.utils.inference_utils import EmbedderService
from src.utils.file_processor import prepare_for_knowledge_base, chunk_by_tokens
from src.domains.knowledge_base.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse
)

from src.core.logging import logger
from src.core.config import (
    INDEXES_DIR
)


router = APIRouter(prefix="/knowledge_base", tags=["knowledge_base"])

@router.get("/{llm_id}/status")
def get_kbAttach_status(llm_id: int, db: Session = Depends(get_db)):
    """Poll KB job status with automatic cleanup for failed jobs.

    Queries KBJob by new_model_id (the specialized LLM created during KB attachment).
    If status="failed", deletes temp LLM entry, associated VectorStore, KnowledgeBase,
    and FAISS index file from disk.

    Args:
        llm_id: ID of the specialized LLM created by create_knowledge_base().
        db: Database session injected by FastAPI.

    Returns:
        dict: {"status": str, "status_updated_at": datetime, "error_message": str | None}

    Raises:
        HTTPException: 404 if KB job not found for given llm_id.

    Example:
        GET /knowledge_base/108/status
        Response: {"status": "running", "status_updated_at": "2024-01-15T10:30:00Z", "error_message": null}
    """
    kb_job = db.query(KBJobModel).filter(KBJobModel.new_model_id == llm_id).first()
    if not kb_job:
        raise HTTPException(status_code=404, detail="KB job not found")

    status = kb_job.status
    updated_at = kb_job.updated_at

    if status == "failed":
        llm = db.query(Llm).filter(Llm.id == llm_id).first()
        if llm:
            if llm.kb_id:
                vector_store = db.query(VectorStore).filter(VectorStore.kb_id == llm.kb_id).first()
                if vector_store:
                    db.delete(vector_store)
                kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == llm.kb_id).first()
                if kb:
                    if kb.index_path:
                        if os.path.exists(kb.index_path):
                            os.remove(kb.index_path)
                    db.delete(kb)
            db.delete(llm)
            
        db.commit()
        db.refresh(kb_job)

    return {
        "status": status,
        "status_updated_at": updated_at,
        "error_message": kb_job.error_message if status == "failed" else None
    }

@router.post("/create", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create or update a Knowledge Base assistant with document ingestion.

    If the base LLM already has a KB attached (is_attached_to_kb=1), updates the existing
    KB with new documents. Otherwise, creates a new specialized LLM entry, KnowledgeBase,
    VectorStore, and queues background task to build FAISS index.

    Workflow:
        1. Validate payload (paths, selectedModel, modelName).
        2. Parse documents via prepare_for_knowledge_base() → text extraction.
        3. Check if base LLM already has KB:
           - YES → Queue update_kb_assistant_with_new_data() background task.
           - NO  → Create new specialized Llm + KB + VectorStore → Queue init_new_kb_assistant().
        4. Background task embeds chunks via sentence-transformers → FAISS IndexIDMap.
        5. Status poll endpoint returns progress until completion.

    Args:
        payload: Request body with selectedModel, modelName, description, paths.
        background_tasks: FastAPI background task queue.
        db: Database session injected by FastAPI.

    Returns:
        KnowledgeBaseResponse: {"msg": str, "model_id": int} with specialized LLM ID.

    Raises:
        HTTPException: 400 if paths empty or invalid, 404 if base LLM not found, 500 on processing errors.

    Example:
        POST /knowledge_base/create
        {
            "selectedModel": 42,
            "modelName": "Financial Reports Assistant",
            "description": "Q1-Q4 2024 earnings",
            "paths": ["/uploads/q1.pdf", "/uploads/q2.pdf"]
        }
        Response: {"msg": "Knowledge Base Assistant is being created.", "model_id": 108}
    """
    logger.info(f"🚀 Received payload: {payload}")
    
    if not payload.paths or not isinstance(payload.paths, list):
        raise HTTPException(
            status_code=400,
            detail="Paths must be a non-empty list."
        )
    logger.info(f"Received paths: {payload.paths}")
    if not payload.selectedModel:
        raise HTTPException(
            status_code=400,
            detail="Selected model ID is required."
        )
    logger.info(f"Selected model ID: {payload.selectedModel}")
    if not payload.modelName:
        raise HTTPException(
            status_code=400,
            detail="Model name is required."
        )
    logger.info(f"Model name: {payload.modelName}")

    try: 
        # Fetch base LLM
        base_llm = db.query(Llm).filter(Llm.id == payload.selectedModel).filter(Llm.local == 1).first()
        if not base_llm:
            error_msg = f"Llm with ID {payload.selectedModel} not found"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        logger.error(f"Error fetching base LLM: {e}")
        raise HTTPException(status_code=500, detail="Error fetching base LLM.")

    try :
        texts = prepare_for_knowledge_base(payload.paths)
        if not texts:
            logger.error("No valid text files found in the provided paths.")
            raise HTTPException(status_code=400, detail="No valid text files found.")
    except Exception as e:
        logger.error(f"Error processing files: {e}")
        raise HTTPException(status_code=500, detail="Error processing files.")
    
    if not payload.description:
        payload.description = ""
    logger.info(f"Description: {payload.description}")

    if not os.path.exists(INDEXES_DIR):
        os.makedirs(INDEXES_DIR)
        logger.info(f"Created INDEXES_DIR at {INDEXES_DIR}")

    try:

        if base_llm.is_attached_to_kb:
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == base_llm.kb_id).first()
            if kb:
                kb_job = KBJobModel(
                    base_model_id=base_llm.id,
                    new_model_id=base_llm.id,
                    kb_id=kb.id,
                    status="pending"
                )
                db.add(kb_job)
                db.commit()
                db.refresh(kb_job)      

                background_tasks.add_task(update_kb_assistant_with_new_data, kb_job.id, kb.id, texts) 

                return KnowledgeBaseResponse(
                    msg="Assistant is being updated with the new data.",
                    model_id=base_llm.id
                )
            
            else:
                logger.error(f"KnowledgeBase with ID {base_llm.kb_id} not found")
                raise HTTPException(status_code=404, detail=f"LLM : {base_llm.name} seems to have a Knowledge Base attached, but the KB was not found.")
        
        # Create new LLM
        new_llm = Llm(
            name=payload.modelName,
            description=payload.description,
            local=1, 
            link=base_llm.link,
            type=base_llm.type,
            is_attached_to_kb=1,
            param_size=base_llm.param_size,  # Copy parameter size from base model
            quantized=base_llm.quantized,  # Copy quantized flag from base model
        )
        db.add(new_llm)
        db.flush()  # To get new_llm.id
        logger.info(f"LLM created with ID: {new_llm.id}")

        # Create Knowledge Base
        kb = KnowledgeBase(
            file_names_list={"file_dropped_paths": payload.paths}
        )
        db.add(kb)
        db.flush()
        new_llm.kb_id = kb.id  # Assign to kb_id (foreign key) not kb (relationship)
        logger.info(f"Knowledge Base created with ID: {kb.id}")

        # Create single VectorStore entry for this KB
        vector_store = VectorStore(
            kb_id=kb.id,
        )
        db.add(vector_store)
        db.flush()

        kb_job = KBJobModel(
            base_model_id=base_llm.id,
            new_model_id=new_llm.id,
            kb_id=kb.id,
            status="pending"
        )
        db.add(kb_job)
        db.commit()
        logger.info(f"Knowledge Base job created with ID: {kb_job.id}")

        background_tasks.add_task(init_new_kb_assistant, kb_job.id, new_llm.id, kb.id, vector_store.id, texts)

        return KnowledgeBaseResponse(
            msg="Knowledge Base Assistant is being created.",
            model_id=new_llm.id
        )
    
    except Exception as e:
        error_msg = f"Error creating KB Assistant:\n{str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )
    finally:
        db.close()

def populate_vector_store(start_counter: int, vectors_data: dict, texts: List[str], index: Any) -> tuple[Any, dict]:
    """Embed text chunks and add to FAISS index with sequential integer IDs.

    Chunks each text via chunk_by_tokens(chunk_size=512), embeds via sentence-transformers
    (384-dim paraphrase-multilingual-MiniLM-L12-v2), and adds to FAISS IndexIDMap with
    custom IDs starting at start_counter. Updates vectors_data JSON mapping ID → chunk text.

    Args:
        start_counter: Starting FAISS ID (0 for new index, max(existing)+1 for updates).
        vectors_data: Existing dict mapping str(ID) → chunk text (mutated in-place).
        texts: List of full-text documents to chunk and embed.
        index: FAISS IndexIDMap to add vectors to (mutated in-place).

    Returns:
        Tuple of (updated FAISS index, updated vectors_data dict).

    Example:
        >>> index = faiss.IndexIDMap(faiss.IndexFlatL2(384))
        >>> vectors_data = {}
        >>> texts = ["This is document 1.", "This is document 2."]
        >>> index, vectors = populate_vector_store(0, vectors_data, texts, index)
        >>> print(index.ntotal)  # Number of vectors added
    """
    embedder = EmbedderService.get_embedder()

    for text in texts:
        if not text.strip():
            continue
        
        logger.info(f"chunking text: {len(text)} characters")
        chunks = chunk_by_tokens(text=text)
        if not chunks:
            logger.error(f"Error chunking text from {text}")
            continue
        logger.info(f"Chunks created: {len(chunks)} for text: {len(text)} characters")
        
        for chunk in chunks:
            if not chunk.strip():
                continue
            logger.info(f"Encoding chunk: {chunk[:50]}...")
            embeddings = embedder.encode(chunk, show_progress_bar=False, convert_to_tensor=True)
            if embeddings is None or len(embeddings) == 0:
                logger.error(f"Error encoding chunk: {chunk[:50]}")
                continue
            logger.info(f"Chunk encoded: {embeddings.shape}")
            
            # Store in vectors_data JSON and add to FAISS index
            vectors_data[str(start_counter)] = chunk
            try:
                index.add_with_ids(embeddings.cpu().numpy().reshape(1, -1), [start_counter])
            except Exception as e:
                logger.error(f"Error adding vector to index: {e}")
                continue
            logger.info(f"Vector added to index with FAISS ID: {start_counter}")
            start_counter += 1

    EmbedderService.cleanup()
    return (index, vectors_data)

def update_kb_assistant_with_new_data(kb_job_id: int, kb_id: int, texts: List[str]) -> Llm:
    """Incrementally update existing KB with new documents (background task).

    Loads existing FAISS index from disk, computes next available ID, embeds new chunks via
    populate_vector_store(), and writes updated index back to disk. On failure, rolls back
    to original index and marks KBJob as failed.

    Args:
        kb_job_id: KBJob database ID to track status.
        kb_id: KnowledgeBase ID to update.
        texts: New full-text documents to chunk and add to existing index.

    Returns:
        Updated Llm entry (base_llm, not new specialized assistant).

    Raises:
        HTTPException: 404 if KBJob/KB/VectorStore not found, 500 on indexing errors.

    Note:
        Runs in BackgroundTasks thread with separate SessionLocal() instance.

    Example:
        >>> background_tasks.add_task(update_kb_assistant_with_new_data, 42, 15, new_texts)
        # Async task updates KB #15 with new_texts, polls KBJob #42 for status
    """
    db = SessionLocal()
    try:
        kb_job = db.query(KBJobModel).filter(KBJobModel.id == kb_job_id).first()
        if not kb_job:
            logger.error(f"KBJob with ID {kb_job_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="KBJob not found")
        kb_job.status = "running"
        kb_job.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        logger.error(f"Error fetching KBJob: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        llm = db.query(Llm).filter(Llm.id == kb_job.base_llm_id).first()
        if not llm:
            logger.error(f"LLM with ID {kb_job.base_llm_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="LLM not found")
    except Exception as e:
        logger.error(f"Error fetching LLM: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            logger.error(f"Knowledge Base with ID {kb_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="Knowledge Base not found")
    except Exception as e:
        logger.error(f"Error fetching Knowledge Base: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        vector_store = db.query(VectorStore).filter(VectorStore.kb_id == kb_id).first()
        if not vector_store:
            logger.error(f"VectorStore associated to KB {kb_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="VectorStore not found")
    except Exception as e:
        logger.error(f"Error fetching VectorStore: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    initial_index = None
    try:
        initial_index = faiss.read_index(kb.index_path)
    except:
        logger.error(f"Error reading initial index")
        raise HTTPException(status_code=404, detail=f"Index attached to LLM {llm.id} could not be read from disk")
    
    base_vectors_data = vector_store.vectors_data

    try:
        index = initial_index
        start_index = max([int(k) for k in base_vectors_data.keys()]) + 1 if base_vectors_data else 0
        try:
            index, new_vectors_data = populate_vector_store(start_counter=start_index, vectors_data=base_vectors_data, texts=texts, index=index)
        except:
            raise
        try:
            faiss.write_index(index, kb.index_path)
        except Exception as e2:
            logger.error(f"Error writing index for KB {kb.id}: {e2}")
            raise

        vector_store.vectors_data = new_vectors_data
        kb_job.status = "completed"
        kb_job.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        logger.error(f"Error during KB update for LLM {llm.id}: {e}")
        kb_job.status = "failed"
        kb_job.updated_at = datetime.now()
        vector_store.vectors_data = base_vectors_data
        db.commit()

        try:
            faiss.write_index(initial_index, kb.index_path)
        except Exception as e2:
            logger.error(f"Error writing index for KB {kb.id}: {e2}")
            raise HTTPException(status_code=404, detail=f"Error writing index for KB {kb.id}: {e2}")
        
    finally:
        db.close()
        
def init_new_kb_assistant(kb_job_id: int, new_llm_id: int, kb_id: int, vector_store_id: int, texts: List[str]) -> Llm:
    """Initialize new Knowledge Base assistant from scratch (background task).

    Complete setup pipeline:
    1. Create FAISS IndexIDMap(IndexFlatL2(384)) for 384-dim embeddings.
    2. Embed all chunks via populate_vector_store() starting at ID=0.
    3. Write index to disk at {INDEXES_DIR}/{kb_id}.index.
    4. Store vectors_data JSON in VectorStore (maps FAISS IDs → chunk text).
    5. Verify index readability + perform test search.
    6. Mark KBJob as completed on success, or failed with cleanup on error.

    Args:
        kb_job_id: KBJob database ID to track status.
        new_llm_id: Specialized LLM ID created for this KB assistant.
        kb_id: KnowledgeBase ID to populate.
        vector_store_id: VectorStore ID to store vectors_data JSON.
        texts: Full-text documents to chunk and embed.

    Returns:
        Newly created specialized Llm entry.

    Raises:
        HTTPException: 404 if entities not found, 500 on FAISS or embedding errors.

    Note:
        Runs in BackgroundTasks thread with separate SessionLocal() instance.
        On failure, cleans up: VectorStore, KnowledgeBase, FAISS index file, specialized Llm.

    Example:
        >>> background_tasks.add_task(init_new_kb_assistant, 42, 108, 15, 23, texts)
        # Creates FAISS index for KB #15, embeds texts, stores in VectorStore #23
    """
    db = SessionLocal()
    try:
        kb_job = db.query(KBJobModel).filter(KBJobModel.id == kb_job_id).first()
        if not kb_job:
            logger.error(f"KBJob with ID {kb_job_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="KBJob not found")
        kb_job.status = "running"
        kb_job.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        logger.error(f"Error fetching KBJob: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        new_llm = db.query(Llm).filter(Llm.id == new_llm_id).first()
        if not new_llm:
            logger.error(f"New LLM with ID {new_llm_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="New LLM not found")
    except Exception as e:
        logger.error(f"Error fetching New LLM: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            logger.error(f"Knowledge Base with ID {kb_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="Knowledge Base not found")
    except Exception as e:
        logger.error(f"Error fetching Knowledge Base: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        vector_store = db.query(VectorStore).filter(VectorStore.id == vector_store_id).first()
        if not vector_store:
            logger.error(f"VectorStore with ID {vector_store_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="VectorStore not found")
    except Exception as e:
        logger.error(f"Error fetching VectorStore: {e}")
        try:
            db.close()
        except Exception as e:
            logger.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        logger.info(f"Creating Index for Knowledge Base {kb.id} with {len(texts)} texts")
        try:
            index = faiss.IndexFlatL2(384)
            index = faiss.IndexIDMap(index)
        except Exception as e:
            logger.error(f"Error creating FAISS index: {e}")
            raise
        logger.info(f"Index created with dimension: {index.d}")

        # Prepare vectors data JSON for the VectorStore
        vectors_data = {}
        index, vectors_data = populate_vector_store(start_counter=0, vectors_data=vectors_data, texts=texts, index=index)

        vector_store.vectors_data = vectors_data
        db.commit()
        logger.info(f"VectorStore created with ID: {vector_store.id}, containing {len(vectors_data)} vectors")

        logger.info(f"Storing index to {INDEXES_DIR}/{kb.id}.index")
        try:
            faiss.write_index(index, os.path.join(INDEXES_DIR, f"{kb.id}.index"))
            kb.index_path = os.path.join(INDEXES_DIR, f"{kb.id}.index")
            db.commit()
            logger.info(f"FAISS index written to disk at {kb.index_path}")
        except:
            logger.error(f"Error writing FAISS index to disk at {kb.index_path}")
            raise

        logger.info(f"Storing Knowledge Base index at {kb.index_path}")

        # ========= VERIFS BEFORE COMMIT =========
        if os.path.exists(kb.index_path):
            logger.info(f"✅ FAISS index file exists at {kb.index_path}")
            try:
                test_index = faiss.read_index(kb.index_path)
                logger.info(f"✅ FAISS index verification: {test_index.ntotal} vectors, dimension {test_index.d}")
            except Exception as e:
                logger.error(f"❌ FAISS index verification failed: {e}")
                raise
        else:
            logger.error(f"❌ FAISS index file not found at {kb.index_path}")
            raise
        
        try:
            db.refresh(kb)
            db.refresh(new_llm)
            db.refresh(vector_store)
            db.flush()
            logger.info(f"✅ Database verification:")
            logger.info(f"   - KB ID: {kb.id}")
            logger.info(f"   - LLM ID: {new_llm.id}, kb_id: {new_llm.kb_id}")
            logger.info(f"   - VectorStore ID: {vector_store.id}, vectors count: {len(vector_store.vectors_data)}")
        except Exception as e:
            logger.error(f"❌ Database verification failed: {e}")
            raise

        try:
            logger.info("Starting minimal search test...")
            
            test_index = faiss.read_index(kb.index_path)
            logger.info(f"✅ Index reload successful: {test_index.ntotal} vectors")
            
            if test_index.ntotal > 0:
                embedder = EmbedderService.get_embedder()
                query_emb = embedder.encode("Ceci est une phrase de test", convert_to_tensor=True)
                logger.info("Phrase test embeddée.")
                q = numpy.ascontiguousarray(
                    query_emb.detach().cpu().numpy().astype("float32")
                ).reshape(1, -1)
                _, I = test_index.search(q, k=1)
                logger.info(f"✅ Basic search successful: found ID {I[0][0]}")
            else:
                logger.warning("⚠️ Index is empty")
                
        except Exception as e:
            logger.error(f"❌ Search test failed: {e}")
            raise
        
        kb_job.status = "completed"
        kb_job.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"🎉 Knowledge Base {kb.id} created successfully with {len(vectors_data)} vectors!")
        
        return new_llm
    
    except Exception as e:
        try:
            if vector_store:
                db.delete(vector_store)

            if kb:
                if kb.index_path and os.path.exists(kb.index_path):
                    os.remove(kb.index_path)
                db.delete(kb)
            
            if new_llm:
                db.delete(new_llm)
            db.commit()

            status = "failed"
            error_msg = f"Error creating KB Assistant:\n{str(e)}"
            logger.error(error_msg)
            kb_job.status = status
            kb_job.error_message = error_msg
            kb_job.updated_at = datetime.utcnow()
            db.commit()
        except Exception as ex:
            logger.error(f"Error updating KBJob status: {ex}")

    finally:
        db.close()