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
from backend.src.core.config import (
    INDEXES_DIR
)


router = APIRouter(prefix="/knowledge_base", tags=["knowledge_base"])

@router.get("/{llm_id}/status")
def get_kbAttach_status(llm_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a kb job during creation of the kb.
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
    """
    Attach a new knowledge base to an assistant.
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
    """
    Initialize the knowledge base assistant by creating the FAISS index and storing vectors.
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