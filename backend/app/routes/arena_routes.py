from datetime import datetime
import logging
from app.schemas.arena_schemas import ArenaQueryPayload
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TextIteratorStreamer,
    StoppingCriteria,
    StoppingCriteriaList,
    BitsAndBytesConfig,
)
import torch, re, threading
from ..database import get_db
from ..models.Llm import Llm
from ..prompting.builder import build_conv_prompt
import os
from dotenv import load_dotenv
load_dotenv()
CACHE_DIR = os.getenv("CACHE_DIR")
from sentence_transformers import SentenceTransformer
import faiss
from ..utils.file_processor import chunk_by_tokens
from ..models.KnowledgeBase import KnowledgeBase
from ..models.VectorStore import VectorStore
from typing import List

router = APIRouter(prefix="/arena", tags=["arena"])

# Optimized BitsAndBytesConfig for Gemma3
"""bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_storage=torch.uint8
)"""
flash_attn_impl = False

MISTRAL_RE = re.compile(
    r"(?:<s>|</s>|\[/?INST\]|\<\|/?(?:assistant|user|system|end)\|\>)"
)

GEMMA_RE = re.compile(
    r"(?:<bos>|</s>|<eos>|"
    r"<start_of_turn>(?:\s*(?:user|model|assistant|system))?|"
    r"<end_of_turn>)"
)

def get_relevant_texts_if_kb(query:str, llm:Llm, db: Session) -> List[str]:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == llm.kb_id).first()

    if not os.path.exists(kb.index_path):
        raise HTTPException(
            status_code=404,
            detail=f"Knowledge Base index not found for LLM {llm.id}"
        )
    try:
        faiss_index = faiss.read_index(kb.index_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read FAISS index for Knowledge Base {kb.id}: {str(e)}"
        )
    if not faiss_index:
        raise HTTPException(
            status_code=404,
            detail=f"FAISS index not found for Knowledge Base {kb.id}"
        )
    
    # Get the VectorStore for this KB
    vector_store = db.query(VectorStore).filter(VectorStore.kb_id == kb.id).first()
    if not vector_store:
        raise HTTPException(
            status_code=404,
            detail=f"VectorStore not found for Knowledge Base {kb.id}"
        )
    
    get_embedder()
    chunks = chunk_by_tokens(text=query)
    relevant_texts = []
    if not chunks or len(chunks) < 1:
        raise HTTPException(
            status_code=400,
            detail="No valid text chunks found in the query."
        )
    else:
        for chunk in chunks:
            if not chunk.strip():
                continue
            try:
                query_emb = embedder.encode(chunk, convert_to_tensor=True)
            except Exception as e:
                logging.error(f"Error embedding chunk: {e}")
                continue
            if query_emb is None or query_emb.numel() == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Error embedding chunk."
                )
            try:
                _, idxs = faiss_index.search(query_emb.cpu().numpy().reshape(1, -1), k=3)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error searching FAISS index: {str(e)}"
                )
            for idx in idxs[0]:  # idxs is 2D array, take first row
                if idx < 0:
                    continue
                try:
                    # Get text from vectors_data JSON using FAISS ID as key
                    faiss_id_str = str(idx)
                    if faiss_id_str in vector_store.vectors_data:
                        relevant_texts.append(vector_store.vectors_data[faiss_id_str])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error fetching vector text: {e}"
                    )
    return relevant_texts

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

# Globals to cache model/tokenizer
embedder = None
_loaded_model = None
_current_tokenizer = None
_loaded_model_id = None

@router.post("/{llm_id}/query")
async def query_arena(
    llm_id: int,
    payload: ArenaQueryPayload,
    db: Session = Depends(get_db)
):
    """
    Stateless arena query optimized for Gemma3:
    - llm_id: ID du modèle
    - payload: { question, temperature?, topP?, maxNewTokens?, customPrompt? }
    """
    question = payload.question
    temperature = payload.temperature or 0.7
    top_p = payload.top_p or 0.95
    max_new_tokens = payload.max_new_tokens or 200
    custom_prompt = payload.custom_prompt or ""
    lang = payload.language or "fr"

    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")
        
    logging.info(f"Querying LLM {llm_id} from DB")
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    logging.info(f"Querying LLM from DB finished")
    
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")

    is_gemma = llm.type == "gemma"

    global _loaded_model, _current_tokenizer, _loaded_model_id
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    try:
        if _loaded_model_id != llm.id or _loaded_model is None:
            start = datetime.now()
            logging.info(f"Loading model {llm.id} from {llm.link}")
            
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16 if is_gemma else torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_storage=torch.uint8
            )

            if llm.type == "mistral":
                attn_impl = "flash_attention_2" if float(torch.version.cuda) >= 11.8 and flash_attn_impl else "sdpa"
            elif llm.type == "gemma":
                attn_impl = "eager"
            else:
                attn_impl = None

            _loaded_model = AutoModelForCausalLM.from_pretrained(
                llm.link,
                local_files_only=True,
                torch_dtype=torch.float16 if not is_gemma else torch.bfloat16,
                quantization_config=bnb_config if not is_gemma else None,
                low_cpu_mem_usage=True if not is_gemma else False,
                attn_implementation=attn_impl,
            )
            
            _current_tokenizer = AutoTokenizer.from_pretrained(
                llm.link, 
                local_files_only=True,
                use_fast=True
            )
            
            _loaded_model_id = llm.id
            _loaded_model.eval()
            _loaded_model.to(device)
            logging.info(f"Model {llm.id} loaded in {datetime.now() - start} seconds")
        else:
            logging.info(f"Model {llm.id} already loaded")
    except Exception as e:
        logging.exception("Failed to load model or tokenizer")
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    context = None

    if llm.is_attached_to_kb:
        
        try:
            relevant_texts = get_relevant_texts_if_kb(question, llm, db)
            if not relevant_texts:
                raise HTTPException(status_code=404, detail="No relevant texts found")
            context = "\n\nAlso: You are attached to a Knowledge Base. Here is context you need to know for this query:\n" + "\n".join(relevant_texts)
        except Exception as e:
            logging.exception("Failed to retrieve Knowledge Base context")
            raise HTTPException(status_code=500, detail=f"Knowledge Base retrieval error: {str(e)}")
        
    prompt_text = build_conv_prompt(
        question=question,
        language=lang,
        max_tokens=max_new_tokens,
        model_type=llm.type,
        custom_sys_prompt=custom_prompt,
        context=context if context else None,
    )
    logging.info("Final prompt to model:\n%s", prompt_text)

    input_ids = _current_tokenizer.encode(prompt_text, return_tensors="pt").to(device)

    if is_gemma:
        eos_token_ids = [1, 106]
    elif llm.type == "mistral":
        eos_token_ids = [4, 2]

    streamer = TextIteratorStreamer(
        _current_tokenizer, skip_prompt=True, skip_special_tokens=True
    )

    def run_generation():
        with torch.no_grad():
            generation_config = {
                "input_ids": input_ids,
                "streamer": streamer,
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": 64,
                "eos_token_id": eos_token_ids,
                "pad_token_id": 0 if is_gemma else None,
                "num_beams": 1,
                "do_sample": True,
            }

            try:
                _loaded_model.generate(**generation_config)
            except Exception as e:
                logging.exception("Generation failed")
                streamer.put(e)

    gen_thread = threading.Thread(target=run_generation)
    gen_thread.start()

    async def event_stream():
        
        assistant_response = ""
        try:
            for new_text in streamer:          
                if llm.type == "mistral":
                    cleaned = MISTRAL_RE.sub("", new_text)
                elif llm.type == "gemma":
                    cleaned = GEMMA_RE.sub("", new_text)
                else:
                    cleaned = new_text
                    
                assistant_response += cleaned
                logging.info(f"Yielding token: {cleaned}")
                if cleaned:
                    yield cleaned

        except Exception as e:
            logging.exception("Streaming failed")
            raise HTTPException(status_code=500, detail="Streaming failed")
        finally:
            gen_thread.join()
            
            logging.info("Generation thread finished")

    return StreamingResponse(event_stream(), media_type="text/plain")