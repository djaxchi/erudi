from datetime import datetime
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db

import os
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")  # Accelerate/vecLib (macOS)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")


from ..schemas.knowledgeBase_schemas import KnowledgeBaseCreate, KnowledgeBaseResponse
from ..models.KnowledgeBase import KnowledgeBase
from ..models.VectorStore import VectorStore
from ..models.Llm import Llm
from ..models.KBJob import KBJobModel
from app.utils.inference_utils import EmbedderService
from ..utils.file_processor import prepare_for_knowledge_base, chunk_by_tokens

import logging
from typing import List
import faiss
faiss.omp_set_num_threads(1)
import numpy as np

from dotenv import load_dotenv
load_dotenv()
INDEXES_DIR = os.getenv("INDEXES_DIR", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge_base")

@router.get("/{llm_id}/status")
def get_kbAttach_status(llm_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a kb job.
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
    logging.info(f"🚀 Received payload: {payload}")
    
    if not payload.paths or not isinstance(payload.paths, list):
        raise HTTPException(
            status_code=400,
            detail="Paths must be a non-empty list."
        )
    logging.info(f"Received paths: {payload.paths}")
    if not payload.selectedModel:
        raise HTTPException(
            status_code=400,
            detail="Selected model ID is required."
        )
    logging.info(f"Selected model ID: {payload.selectedModel}")
    if not payload.modelName:
        raise HTTPException(
            status_code=400,
            detail="Model name is required."
        )
    logging.info(f"Model name: {payload.modelName}")

    try: 
        # Fetch base LLM
        base_llm = db.query(Llm).filter(Llm.id == payload.selectedModel).filter(Llm.local == 1).first()
        if not base_llm:
            error_msg = f"Llm with ID {payload.selectedModel} not found"
            logging.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        logging.error(f"Error fetching base LLM: {e}")
        raise HTTPException(status_code=500, detail="Error fetching base LLM.")

    try :
        texts = prepare_for_knowledge_base(payload.paths)
        if not texts:
            logging.error("No valid text files found in the provided paths.")
            raise HTTPException(status_code=400, detail="No valid text files found.")
    except Exception as e:
        logging.error(f"Error processing files: {e}")
        raise HTTPException(status_code=500, detail="Error processing files.")
    
    if not payload.description:
        payload.description = ""
    logging.info(f"Description: {payload.description}")

    if not os.path.exists(INDEXES_DIR):
        os.makedirs(INDEXES_DIR)
        logging.info(f"Created INDEXES_DIR at {INDEXES_DIR}")

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

                background_tasks.add_task(update_kb_assistant_with_new_data, kb_job.id, kb.id, texts, db) 

                return KnowledgeBaseResponse(
                    msg="Assistant is being updated with the new data.",
                    model_id=base_llm.id
                )
            
            else:
                logging.error(f"KnowledgeBase with ID {base_llm.kb_id} not found")
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
        logging.info(f"Knowledge Base job created with ID: {kb_job.id}")

        background_tasks.add_task(init_new_kb_assistant, kb_job.id, new_llm.id, kb.id, vector_store.id, texts, db)

        return KnowledgeBaseResponse(
            msg="Knowledge Base Assistant is being created.",
            model_id=new_llm.id
        )
    
    except Exception as e:
        error_msg = f"Error creating KB Assistant:\n{str(e)}"
        logging.error(error_msg)
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
        
        logging.info(f"chunking text: {len(text)} characters")
        chunks = chunk_by_tokens(text=text)
        if not chunks:
            logging.error(f"Error chunking text from {text}")
            continue
        logging.info(f"Chunks created: {len(chunks)} for text: {len(text)} characters")
        
        for chunk in chunks:
            if not chunk.strip():
                continue
            logging.info(f"Encoding chunk: {chunk[:50]}...")
            embeddings = embedder.encode(chunk, show_progress_bar=False, convert_to_tensor=True)
            if embeddings is None or len(embeddings) == 0:
                logging.error(f"Error encoding chunk: {chunk[:50]}")
                continue
            logging.info(f"Chunk encoded: {embeddings.shape}")
            
            # Store in vectors_data JSON and add to FAISS index
            vectors_data[str(start_counter)] = chunk
            try:
                index.add_with_ids(embeddings.cpu().numpy().reshape(1, -1), [start_counter])
            except Exception as e:
                logging.error(f"Error adding vector to index: {e}")
                continue
            logging.info(f"Vector added to index with FAISS ID: {start_counter}")
            start_counter += 1

    EmbedderService.cleanup()
    return (index, vectors_data)

def update_kb_assistant_with_new_data(kb_job_id: int, kb_id: int, texts: List[str], db: Session) -> Llm:
    try:
        kb_job = db.query(KBJobModel).filter(KBJobModel.id == kb_job_id).first()
        if not kb_job:
            logging.error(f"KBJob with ID {kb_job_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="KBJob not found")
        kb_job.status = "running"
        kb_job.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        logging.error(f"Error fetching KBJob: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        llm = db.query(Llm).filter(Llm.id == kb_job.base_llm_id).first()
        if not llm:
            logging.error(f"LLM with ID {kb_job.base_llm_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="LLM not found")
    except Exception as e:
        logging.error(f"Error fetching LLM: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            logging.error(f"Knowledge Base with ID {kb_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="Knowledge Base not found")
    except Exception as e:
        logging.error(f"Error fetching Knowledge Base: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        vector_store = db.query(VectorStore).filter(VectorStore.kb_id == kb_id).first()
        if not vector_store:
            logging.error(f"VectorStore associated to KB {kb_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="VectorStore not found")
    except Exception as e:
        logging.error(f"Error fetching VectorStore: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    initial_index = None
    try:
        initial_index = faiss.read_index(kb.index_path)
    except:
        logging.error(f"Error reading initial index")
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
            logging.error(f"Error writing index for KB {kb.id}: {e2}")
            raise

        vector_store.vectors_data = new_vectors_data
        kb_job.status = "completed"
        kb_job.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        logging.error(f"Error during KB update for LLM {llm.id}: {e}")
        kb_job.status = "failed"
        kb_job.updated_at = datetime.now()
        vector_store.vectors_data = base_vectors_data
        db.commit()

        try:
            faiss.write_index(initial_index, kb.index_path)
        except Exception as e2:
            logging.error(f"Error writing index for KB {kb.id}: {e2}")
            raise HTTPException(status_code=404, detail=f"Error writing index for KB {kb.id}: {e2}")
        
    finally:
        db.close()
        
def init_new_kb_assistant(kb_job_id: int, new_llm_id: int, kb_id: int, vector_store_id: int, texts: List[str], db: Session) -> Llm:
    """
    Initialize the knowledge base assistant by creating the FAISS index and storing vectors.
    """
    try:
        kb_job = db.query(KBJobModel).filter(KBJobModel.id == kb_job_id).first()
        if not kb_job:
            logging.error(f"KBJob with ID {kb_job_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="KBJob not found")
        kb_job.status = "running"
        kb_job.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        logging.error(f"Error fetching KBJob: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        new_llm = db.query(Llm).filter(Llm.id == new_llm_id).first()
        if not new_llm:
            logging.error(f"New LLM with ID {new_llm_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="New LLM not found")
    except Exception as e:
        logging.error(f"Error fetching New LLM: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            logging.error(f"Knowledge Base with ID {kb_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="Knowledge Base not found")
    except Exception as e:
        logging.error(f"Error fetching Knowledge Base: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        vector_store = db.query(VectorStore).filter(VectorStore.id == vector_store_id).first()
        if not vector_store:
            logging.error(f"VectorStore with ID {vector_store_id} not found")
            db.close()
            raise HTTPException(status_code=404, detail="VectorStore not found")
    except Exception as e:
        logging.error(f"Error fetching VectorStore: {e}")
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error rolling back DB session: {e}")
            raise HTTPException(status_code=500, detail=f"Error closing DB session : {e}")
        raise HTTPException(status_code=404, detail=f"Error manipulating DB session : {e}")

    try:
        logging.info(f"Creating Index for Knowledge Base {kb.id} with {len(texts)} texts")
        try:
            index = faiss.IndexFlatL2(384)
            index = faiss.IndexIDMap(index)
        except Exception as e:
            logging.error(f"Error creating FAISS index: {e}")
            raise
        logging.info(f"Index created with dimension: {index.d}")

        # Prepare vectors data JSON for the VectorStore
        vectors_data = {}
        index, vectors_data = populate_vector_store(start_counter=0, vectors_data=vectors_data, texts=texts, index=index)

        vector_store.vectors_data = vectors_data
        db.commit()
        logging.info(f"VectorStore created with ID: {vector_store.id}, containing {len(vectors_data)} vectors")

        logging.info(f"Storing index to {INDEXES_DIR}/{kb.id}.index")
        try:
            faiss.write_index(index, os.path.join(INDEXES_DIR, f"{kb.id}.index"))
            kb.index_path = os.path.join(INDEXES_DIR, f"{kb.id}.index")
            db.commit()
            logging.info(f"FAISS index written to disk at {kb.index_path}")
        except:
            logging.error(f"Error writing FAISS index to disk at {kb.index_path}")
            raise

        logging.info(f"Storing Knowledge Base index at {kb.index_path}")

        # ========= VERIFS BEFORE COMMIT =========
        if os.path.exists(kb.index_path):
            logging.info(f"✅ FAISS index file exists at {kb.index_path}")
            try:
                test_index = faiss.read_index(kb.index_path)
                logging.info(f"✅ FAISS index verification: {test_index.ntotal} vectors, dimension {test_index.d}")
            except Exception as e:
                logging.error(f"❌ FAISS index verification failed: {e}")
                raise
        else:
            logging.error(f"❌ FAISS index file not found at {kb.index_path}")
            raise
        
        try:
            db.refresh(kb)
            db.refresh(new_llm)
            db.refresh(vector_store)
            db.flush()
            logging.info(f"✅ Database verification:")
            logging.info(f"   - KB ID: {kb.id}")
            logging.info(f"   - LLM ID: {new_llm.id}, kb_id: {new_llm.kb_id}")
            logging.info(f"   - VectorStore ID: {vector_store.id}, vectors count: {len(vector_store.vectors_data)}")
        except Exception as e:
            logging.error(f"❌ Database verification failed: {e}")
            raise

        try:
            logging.info("Starting minimal search test...")
            
            test_index = faiss.read_index(kb.index_path)
            logging.info(f"✅ Index reload successful: {test_index.ntotal} vectors")
            
            if test_index.ntotal > 0:
                first_vector = np.zeros((1, test_index.d), dtype='float32')
                D, I = test_index.search(first_vector, 1)
                logging.info(f"✅ Basic search successful: found ID {I[0][0]}")
            else:
                logging.warning("⚠️ Index is empty")
                
        except Exception as e:
            logging.error(f"❌ Search test failed: {e}")
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
            logging.error(error_msg)
            kb_job.status = status
            kb_job.error_message = error_msg
            kb_job.updated_at = datetime.utcnow()
            db.commit()
        except Exception as ex:
            logging.error(f"Error updating KBJob status: {ex}")

    finally:
        db.close()