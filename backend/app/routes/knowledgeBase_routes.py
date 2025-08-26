from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import SessionLocal, get_db

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
from ..utils.file_processor import prepare_for_knowledge_base, chunk_by_tokens

import logging
from typing import List
import faiss
faiss.omp_set_num_threads(1)
import torch
import numpy as np

from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
load_dotenv()
CACHE_DIR = os.getenv("CACHE_DIR")
INDEXES_DIR = os.getenv("INDEXES_DIR")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge_base")

embedder = None

def get_embedder():
        global embedder
        if embedder is None:
            logging.info("Loading the Embedder")
            os.makedirs(CACHE_DIR, exist_ok=True)
            embedder = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                cache_folder=CACHE_DIR
            )
            logging.info("Embedder loaded")
        return embedder



@router.post("/create", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    payload: KnowledgeBaseCreate, 
    db: Session = Depends(get_db)
):
    """
    Create a new knowledge base.
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
    if not payload.description:
        payload.description = ""
    logging.info(f"Description: {payload.description}")
    if not os.path.exists(INDEXES_DIR):
        os.makedirs(INDEXES_DIR)

    try:
        # Fetch base LLM
        base_llm = db.query(Llm).filter(Llm.id == payload.selectedModel).filter(Llm.local == 1).first()
        if not base_llm:
            error_msg = f"Llm with ID {payload.selectedModel} not found"
            logging.error(error_msg)
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )

        # Create new LLM
        new_llm = Llm(
            name=payload.modelName,
            description=payload.description,
            local=1, 
            link=base_llm.link,
            type=base_llm.type,
            is_attached_to_kb=1
        )
        db.add(new_llm)
        db.commit()
        db.refresh(new_llm)
        logger.info(f"LLM created with ID: {new_llm.id}")

        # Create Knowledge Base
        kb = KnowledgeBase(
            index_path=INDEXES_DIR,
            file_names_list={"file_dropped_paths": payload.paths}
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        new_llm.kb_id = kb.id  # Assign to kb_id (foreign key) not kb (relationship)
        db.commit()
        db.refresh(new_llm)
        
        logger.info(f"Knowledge Base created with ID: {kb.id}")

        # Process files and create vectors
        texts = prepare_for_knowledge_base(payload.paths)
        if not texts:
            raise HTTPException(
                status_code=400,
                detail="No valid text files found in the provided paths."
            )
        
        global embedder
        if not embedder:
            embedder = get_embedder()
        logging.info(f"Creating Index for Knowledge Base {kb.id} with {len(texts)} texts")
        index = faiss.IndexFlatL2(384)
        index = faiss.IndexIDMap(index)
        logging.info(f"Index created with dimension: {index.d}")

        # Prepare vectors data JSON for the VectorStore
        vectors_data = {}
        faiss_id_counter = 0

        for text in texts:
            if not text.strip():
                continue
            try:
                logging.info(f"chunking text: {len(text)} characters")
                chunks = chunk_by_tokens(text=text)
                logging.info(f"Chunks created: {len(chunks)} for text: {len(text)} characters")
            except Exception as e:
                logging.error(f"Error chunking text from {text}: {e}")
                continue
            if not chunks:
                continue
            for chunk in chunks:
                if not chunk.strip():
                    continue
                try:
                    logging.info(f"Encoding chunk: {chunk[:50]}...")
                    embeddings = embedder.encode(chunk, show_progress_bar=False, convert_to_tensor=True)
                    logging.info(f"Chunk encoded: {embeddings.shape}")
                    
                    # Store in vectors_data JSON and add to FAISS index
                    vectors_data[str(faiss_id_counter)] = chunk
                    index.add_with_ids(embeddings.cpu().numpy().reshape(1, -1), [faiss_id_counter])
                    logging.info(f"Vector added to index with FAISS ID: {faiss_id_counter}")
                    faiss_id_counter += 1
                except Exception as e:
                    logging.error(f"Error encoding chunk: {e}")
                    continue

        # Create single VectorStore entry for this KB
        vector_store = VectorStore(
            kb_id=kb.id,
            vectors_data=vectors_data
        )
        db.add(vector_store)
        db.commit()
        db.refresh(vector_store)
        logging.info(f"VectorStore created with ID: {vector_store.id}, containing {len(vectors_data)} vectors")

        logging.info(f"Storing index to {INDEXES_DIR}/{kb.id}.index")        
        faiss.write_index(index, os.path.join(INDEXES_DIR, f"{kb.id}.index"))
        kb.index_path = os.path.join(INDEXES_DIR, f"{kb.id}.index")
        db.commit()
        logging.info(f"Storing Knowledge Base index at {kb.index_path}")
        
        # AJOUTER CES VÉRIFICATIONS
        # 1. Vérifier que le fichier FAISS existe et est lisible
        if os.path.exists(kb.index_path):
            try:
                test_index = faiss.read_index(kb.index_path)
                logging.info(f"✅ FAISS index verification: {test_index.ntotal} vectors, dimension {test_index.d}")
            except Exception as e:
                logging.error(f"❌ FAISS index verification failed: {e}")
        else:
            logging.error(f"❌ FAISS index file not found at {kb.index_path}")
        
        # 2. Vérifier la base de données
        db.refresh(kb)
        db.refresh(new_llm)
        logging.info(f"✅ Database verification:")
        logging.info(f"   - KB ID: {kb.id}")
        logging.info(f"   - LLM ID: {new_llm.id}, kb_id: {new_llm.kb_id}")
        logging.info(f"   - VectorStore ID: {vector_store.id}, vectors count: {len(vector_store.vectors_data)}")
        
        # 3. Test rapide de recherche (VERSION ULTRA-SIMPLE)
        try:
            logging.info("Starting minimal search test...")
            
            # Juste vérifier qu'on peut recharger l'index
            test_index = faiss.read_index(kb.index_path)
            logging.info(f"✅ Index reload successful: {test_index.ntotal} vectors")
            
            # Si l'index n'est pas vide, faire un test minimal
            if test_index.ntotal > 0:
                # Prendre le premier vecteur de l'index comme query
                first_vector = np.zeros((1, test_index.d), dtype='float32')
                D, I = test_index.search(first_vector, 1)
                logging.info(f"✅ Basic search successful: found ID {I[0][0]}")
            else:
                logging.warning("⚠️ Index is empty")
                
        except Exception as e:
            logging.error(f"❌ Search test failed: {e}")
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")
            # Ne pas faire crasher, juste logger l'erreur

        # MAINTENANT supprimer l'embedder et vider le cache
        if embedder:
            del embedder
            embedder = None  # Reset to None for safety
            # Vider le cache selon le device disponible
            try:
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                elif torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except AttributeError:
                # Fallback si les méthodes n'existent pas
                pass
        
        logger.info(f"🎉 Knowledge Base {kb.id} created successfully with {faiss_id_counter} vectors!")
        
        return KnowledgeBaseResponse(
            model_id=new_llm.id,
            kb_id=kb.id
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        error_msg = f"Error creating Assistant: {str(e)}"
        logging.error(error_msg)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )
    finally:
        db.close()