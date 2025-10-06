import gc

from ..models.VectorStore import VectorStore

from ..models.KnowledgeBase import KnowledgeBase
from ..schemas.message_schemas import MessageCreate, MessageResponse
from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
import torch
import mlx_lm
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer, QuantoConfig
import mlx.core as mx
import mlx_lm
import logging
from typing import List
from ..database import get_db
from ..utils.file_processor import chunk_by_tokens
from app.utils.hardware_info import build_max_memory
from ..models.Conversation import Conversation
from ..models.Llm import Llm
from ..models.Message import Message
from ..schemas.conversation_schemas import (
    ConversationCreate,
    ConversationDeleteBulk,
    ConversationQuery,
    ConversationQueryResponse,
    ConversationResponse,
    ConversationUpdate,
    ConversationWithMessagesResponse,
)
import os

os.environ.setdefault("VECLIB_MAXIMUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("MKL_NUM_THREADS","1")
os.environ.setdefault("NUMEXPR_NUM_THREADS","1")


import threading
from fastapi.responses import StreamingResponse
from faiss import IndexFlatL2
import faiss
faiss.omp_set_num_threads(1)
from sentence_transformers import SentenceTransformer
import numpy as np
from ..prompting.builder import build_conv_prompt
import re
from dotenv import load_dotenv

load_dotenv()
CACHE_DIR = os.getenv("CACHE_DIR")

_loaded_model = None
_current_tokenizer = None
_loaded_model_id = None
_embedder = None
# _is_quant_on_current_load = None
_conversation_summary_cache = {}
# _device = "cpu"

MISTRAL_RE = re.compile(
    r"(?:<s>|</s>|\[/?INST\]|\<\|/?(?:assistant|user|system|end)\|\>)"
)

GEMMA_RE = re.compile(
    r"(?:<bos>|</s>|<eos>|"
    r"<start_of_turn>(?:\s*(?:user|model|assistant|system))?|"
    r"<end_of_turn>)"
)


def get_relevant_texts_if_kb(query: str, llm: Llm, db: Session) -> List[str]:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == llm.kb_id).first()

    if not os.path.exists(kb.index_path):
        raise HTTPException(
            status_code=404, detail=f"Knowledge Base index not found for LLM {llm.id}"
        )
    try:
        faiss_index = faiss.read_index(kb.index_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read FAISS index for Knowledge Base {kb.id}: {str(e)}",
        )
    if not faiss_index:
        raise HTTPException(
            status_code=404, detail=f"FAISS index not found for Knowledge Base {kb.id}"
        )

    # Get the VectorStore for this KB
    vector_store = db.query(VectorStore).filter(VectorStore.kb_id == kb.id).first()
    if not vector_store:
        raise HTTPException(
            status_code=404, detail=f"VectorStore not found for Knowledge Base {kb.id}"
        )

    get_embedder()
    chunks = chunk_by_tokens(text=query)
    logging.info("Chunks created for query.")
    relevant_texts = []
    if not chunks or len(chunks) < 1:
        raise HTTPException(
            status_code=400, detail="No valid text chunks found in the query."
        )
    else:
        for chunk in chunks:
            if not chunk.strip():
                continue
            try:
                logging.info(f"Encoding query chunk: {chunk[:50]}...")
                query_emb = _embedder.encode(chunk, convert_to_tensor=True)
                logging.info(f"Query chunk encoded: {query_emb.shape}")
            except Exception as e:
                logging.error(f"Error embedding chunk: {e}")
                continue
            if query_emb is None or query_emb.numel() == 0:
                raise HTTPException(status_code=400, detail="Error embedding chunk.")
            try:
                logging.info(f"Searching FAISS index for query chunk...")
                # _, idxs = faiss_index.search(
                #     query_emb.cpu().numpy().reshape(1, -1), k=3
                # )
                q = np.ascontiguousarray(
                    query_emb.detach().cpu().numpy().astype("float32")
                ).reshape(1, -1)

                D, I = faiss_index.search(q, k=3)
                logging.info(f"FAISS index search completed, found {len(I[0])} results.")
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error searching FAISS index: {str(e)}"
                )
            logging.info(f"FAISS index search returned {len(I[0])} IDs.")
            for idx in I[0]:  # I is 2D array, take first row
                if idx < 0:
                    continue
                try:
                    logging.info(f"Fetching text for FAISS ID: {idx}")
                    # Get text from vectors_data JSON using FAISS ID as key
                    faiss_id_str = str(idx)
                    if faiss_id_str in vector_store.vectors_data:
                        relevant_texts.append(vector_store.vectors_data[faiss_id_str])
                except Exception as e:
                    raise HTTPException(
                        status_code=500, detail=f"Error fetching vector text: {e}"
                    )
    return relevant_texts


def get_embedder():
    global _embedder
    if _embedder is None:
        logging.info("Loading the Embedder")
        os.makedirs(CACHE_DIR, exist_ok=True)
        _embedder = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            cache_folder=CACHE_DIR,
        )
        logging.info("Embedder loaded")
    return _embedder


router = APIRouter()


def clear_memory():
    """Clear GPU memory and cache for macOS"""
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
        torch.mps.synchronize()
    gc.collect()


def load_model(llm: Llm) -> None:
    global _loaded_model, _current_tokenizer, _loaded_model_id
    if llm.id == _loaded_model_id and _loaded_model is not None and _current_tokenizer is not None:
        logging.info(f"Model {llm.id} already loaded")
        return
    print("Loading MLX model and tokenizer...")
    start = datetime.now()
    _loaded_model_id = llm.id
    _loaded_model, _current_tokenizer = mlx_lm.load(llm.link)
    print(f"Model and tokenizer loaded in {datetime.now() - start}")


clear_memory()

@router.get(
    "/conversations/{conversation_id}/fetch_messages",
    response_model=List[MessageResponse],
)
async def get_messages_by_conversation(
    conversation_id: int, db: Session = Depends(get_db)
):
    """
    Fetch all messages for a specific conversation.
    """
    messages = (
        db.query(Message).filter(Message.conversation_id == conversation_id).all()
    )
    return messages


@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific message by its ID.
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()
    return {"message": "Message deleted successfully"}


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_all_conversations(db: Session = Depends(get_db)):
    """
    Fetch all conversations.
    """
    try:
        conversations = db.query(Conversation).all()
        return conversations
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse
)
async def get_conversation_by_id(conversation_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single conversation by its ID, including messages.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
):
    """Create a new conversation for a specific LLM (body JSON)."""

    conversation = Conversation(
        llm_id=payload.llm_id,
        name="New Conversation",
        temperature=payload.temperature,
        top_p=payload.top_p,
        max_tokens=payload.max_tokens,
        quantize=payload.quantize,
        custom_prompt=payload.custom_prompt
    )
    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create conversation: {str(e)}",
        )
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Delete a conversation by its ID.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    global _conversation_summary_cache
    if conversation_id in _conversation_summary_cache:
        del _conversation_summary_cache[conversation_id]
        logging.info(
            f"Cleared summary cache for deleted conversation {conversation_id}"
        )

    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully"}


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
):
    """Update conversation fields (name and llm_id)."""

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    updated = False

    if payload.name is not None and payload.name != conversation.name:
        conversation.name = payload.name
        updated = True

    if payload.llm_id is not None and payload.llm_id != conversation.llm_id:
        conversation.llm_id = payload.llm_id
        updated = True

    if payload.temperature is not None and payload.temperature != conversation.temperature:
        conversation.temperature = payload.temperature
        updated = True

    if payload.top_p is not None and payload.top_p != conversation.top_p:
        conversation.top_p = payload.top_p
        updated = True

    if payload.max_tokens is not None and payload.max_tokens != conversation.max_tokens:
        conversation.max_tokens = payload.max_tokens
        updated = True

    if payload.quantize is not None and payload.quantize != conversation.quantize:
        conversation.quantize = payload.quantize
        updated = True

    if payload.custom_prompt is not None and payload.custom_prompt != conversation.custom_prompt:
        conversation.custom_prompt = payload.custom_prompt
        updated = True

    if updated:
        try:
            db.commit()
            db.refresh(conversation)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Could not update conversation: {str(e)}",
            )

    return conversation


def get_conversation_history(db: Session, conversation_id: int) -> List[tuple]:
    try:
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        messages_to_be_returned = []

        if len(messages) == 0:
            return messages_to_be_returned

        for msg in messages:
            messages_to_be_returned.append((msg.sender, msg.content))

        return messages_to_be_returned
    except Exception as e:
        logging.exception(f"Error retrieving conversation history: {e}")
        return []


def get_prompting_strategy(param_size: int) -> dict:
    """
    Determine prompting strategy based on model parameter size.
    
    Args:
        param_size (int): Model parameter size in billions (2, 4, 8, 16, etc.)
    
    Returns:
        dict: Strategy configuration with the following keys:
            - use_system_prompt (bool): Include system prompt
            - use_custom_prompt (bool): Include custom prompt
            - max_history_turns (int): Maximum number of conversation turns to include
            - use_short_term_memory (bool): Include recent messages
            - use_middle_term_memory (bool): Include semantically relevant messages
            - use_long_term_memory (bool): Include conversation summary
            - use_kb_basic (bool): Use basic knowledge base retrieval
            - use_kb_enhanced (bool): Use enhanced knowledge base retrieval with more context
            - kb_top_k (int): Number of KB chunks to retrieve
    """
    
    if param_size < 2:
        # Ultra-lightweight strategy for tiny models (<2B)
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 1,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "use_long_term_memory": False,
            "use_kb_basic": False,
            "use_kb_enhanced": False,
            "kb_top_k": 0,
        }
    elif param_size < 4:
        # Lightweight strategy for small models (2-3B)
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 1,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "use_long_term_memory": False,
            "use_kb_basic": False,
            "use_kb_enhanced": False,
            "kb_top_k": 0,
        }
    elif param_size < 8:
        # Medium strategy for 4-7B models
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 2,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "use_long_term_memory": False,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 2,
        }
    elif param_size < 16:
        # Full strategy for 8-15B models
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "use_long_term_memory": True,
            "use_kb_basic": False,
            "use_kb_enhanced": True,
            "kb_top_k": 3,
        }
    else:
        # Maximum strategy for large models (16B+)
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 5,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "use_long_term_memory": True,
            "use_kb_basic": False,
            "use_kb_enhanced": True,
            "kb_top_k": 5,
        }


def retrieve_context(
    query: str,
    conversation_history: List,
    conversation_id: int,
    llm: Llm,
    db: Session,
    strategy: dict,
    top_k: int = 3,
    n_last_turns: int = 1,
    model_type: str = "mistral",
) -> dict :
    """
    Retrieve relevant context from the conversation history based on semantic similarity and recency.
    Uses SentenceTransformer for embeddings and FAISS for similarity search.
    Args:
        query (str): The user's query.
        conversation_history (list): List of (sender, message) tuples.
        conversation_id (int): The ID of the conversation for caching purposes.
        llm (Llm): The LLM model object.
        db (Session): Database session.
        strategy (dict): Prompting strategy configuration based on model size.
        top_k (int): Number of semantically relevant turns to retrieve.
        n_last_turns (int): Number of last turns to include.
        model_type (str): The type of model to use for prompt engineering.
    Returns:
        dict :
        {   context_str (str) : Formatted context string.
            long_term_memory (str) : long-term-memory (conversation summary by llm)
            middle_term_memory (list) : middle-term-memory (top_k most relevant turns relative to the user query)
        }
    """

    context = {
        "context_str": None,
        "long_term_memory": None,
        "middle_term_memory": None,
        "kb_context": None,
    }

    def get_cached_summary(conversation_id: int, current_message_count: int):
        """Get cached summary or determine if regeneration is needed."""
        global _conversation_summary_cache

        if conversation_id not in _conversation_summary_cache:
            return None, True

        cache_entry = _conversation_summary_cache[conversation_id]
        cached_count = cache_entry["message_count"]

        if current_message_count >= cached_count * 2:
            logging.info(
                f"Summary cache expired for conversation {conversation_id}: {cached_count} -> {current_message_count} messages"
            )
            return None, True

        logging.info(
            f"Using cached summary for conversation {conversation_id}: {cached_count} messages"
        )
        return cache_entry["summary"], False

    def cache_summary(conversation_id: int, summary: str, message_count: int):
        """Cache the generated summary."""
        global _conversation_summary_cache
        _conversation_summary_cache[conversation_id] = {
            "summary": summary,
            "message_count": message_count,
            "generated_at": datetime.now(),
        }
        logging.info(
            f"Cached summary for conversation {conversation_id} with {message_count} messages"
        )

    def generate_conversation_summary(history, model_type="mistral"):
        """
        Generate a quick summary of the conversation history.
        Args:
            history (list): List of (sender, message) tuples.
            model_type (str): The type of model to use for summarization.
        Returns:
            str: The generated summary.
        """
        if not _loaded_model or not _current_tokenizer or len(history) < 10:
            return ""

        conv_text = ""
        for sender, msg in history:
            role = "User" if sender == "user" else "Assistant"
            conv_text += f"{role}: {msg}\n"

        # THIS IS TO FIX IN ORDER TO KEEP ALL OF TRHE CONTEXT, BY CHUNKS AND NOT BY TRUNCKING AFTER 4000 CHAR
        if len(conv_text) > 4000:
            conv_text = conv_text[:4000] + "..."

        # mistral_summary_prompt = f"""<|system|>You are a conversation summarizer. Create a concise summary of the key topics, decisions, and important information discussed in this conversation. Keep it under 100 words.<|end|>

        # <|user|>Summarize this conversation:

        # {conv_text}

        # Summary:<|end|>
        # <|assistant|>"""

        # gemma_summary_prompt = f"""<start_of_turn>user
        # You are a conversation summarizer. Create a concise summary of the key topics, decisions, and important information discussed in this conversation. Keep it under 100 words.

        # Summarize this conversation:

        # {conv_text}

        # Summary:<end_of_turn>
        # <start_of_turn>model
        # """
        
        summary_sys_prompt = f"""You are a conversation summarizer. Create a concise summary of the key topics, decisions, and important information discussed in this conversation. Keep it under 100 words. No formatting needed, only a few phrases."""
        summary_user_prompt = f"""Summarize this conversation:

        {conv_text}

        Summary:"""

        try:
            """if model_type == "mistral":
                input_ids = _current_tokenizer.encode(
                    mistral_summary_prompt, return_tensors="pt"
                ).to(_device)
                end_ids = [4, 2]
            elif model_type == "gemma":
                input_ids = _current_tokenizer.encode(
                    gemma_summary_prompt, return_tensors="pt"
                ).to(_device)
                end_ids = [1, 106]

            with torch.no_grad():
                output = _loaded_model.generate(
                    input_ids,
                    max_new_tokens=150,
                    temperature=0.1,
                    top_p=0.5,
                    num_beams=1,
                    pad_token_id=0 if model_type == "gemma" else None,
                    end_token_id=end_ids,
                    do_sample=True,
                )

            full_response = _current_tokenizer.decode(
                output[0], skip_special_tokens=True
            )

            if model_type == "mistral":
                summary = MISTRAL_RE.sub("", full_response)
            elif model_type.startswith("gemma"):
                summary = GEMMA_RE.sub("", full_response)
            else:
                summary = full_response
            """

            # Model Loading
            try:
                # Merge system prompt into user message for models that don't support system role
                merged_summary_prompt = f"{summary_sys_prompt}\n\n{summary_user_prompt}"
                prompt_tokens = _current_tokenizer.apply_chat_template([{"role": "user", "content": merged_summary_prompt}])
                sampler = mlx_lm.sample_utils.make_sampler(
                    0.1,
                    0.5,
                    min_p=0.0,
                    top_k=64,
                    xtc_special_tokens=_current_tokenizer.encode("\n") + list(_current_tokenizer.eos_token_ids)
                )
            except :
                logging.exception("Failed to tokenize prompt")
                raise
            
            summary = mlx_lm.generate(
                _loaded_model,
                _current_tokenizer,
                prompt_tokens,
                max_tokens=150,
                sampler=sampler,
                prompt_cache=None
            )

            return summary

        except Exception as e:
            logging.exception(f"Summary generation failed: {e}")
            return ""

    context_lines = []
    current_message_count = len(conversation_history)

    # Long-term memory (Conversation summary) - only if strategy allows
    summary_threshold = n_last_turns * 2 * 2 
    if (strategy["use_long_term_memory"] and 
        len(conversation_history) > summary_threshold and 
        _loaded_model and 
        _current_tokenizer):
        cached_summary, need_regenerate = get_cached_summary(
            conversation_id, current_message_count
        )

        if need_regenerate:
            logging.info(
                f"Generating new conversation summary for {len(conversation_history)} messages"
            )
            long_term_memory = generate_conversation_summary(conversation_history, model_type=model_type)
            if long_term_memory:
                cache_summary(conversation_id, long_term_memory, current_message_count + 1)
        else:
            long_term_memory = cached_summary

        if long_term_memory:
            context_lines.append("  - Conversation Summary:\n")
            context_lines.append(f"{long_term_memory}")
            context_lines.append("")
            context["long_term_memory"] = long_term_memory

    n_recent = n_last_turns * 2
    if len(conversation_history) >= n_recent + 4:
        semantic_history = conversation_history[:-n_recent]
    else:
        semantic_history = []

    # Middle-term memory (Semantic context) - only if strategy allows
    if strategy["use_middle_term_memory"] and len(semantic_history) >= 2:
        n_to_retrieve = top_k if len(semantic_history) >= 2*top_k else int(len(semantic_history)/2)
        get_embedder()
        query_emb = _embedder.encode(query, convert_to_tensor=True)
        messages = [msg[1] for msg in semantic_history]
        msg_embs = _embedder.encode(messages, convert_to_tensor=False)
        index = IndexFlatL2(len(msg_embs[0]))
        index.add(np.array(msg_embs))
        _, idxs = index.search(
            np.array([query_emb.cpu().numpy()]), k=n_to_retrieve
        )

        used = set()
        semantic_lines = []
        for idx in idxs[0]:
            sender, msg = semantic_history[idx]
            if msg in used:
                continue
            used.add(msg)
            if sender == "user" and idx + 1 < len(semantic_history):
                next_sender, next_msg = semantic_history[idx + 1]
                if next_msg not in used:
                    semantic_lines.append(f"[user]: {msg}")
                    used.add(next_msg)
                    semantic_lines.append(f"[assistant]: {next_msg}")
            elif sender != "user" and idx > 0:
                prev_sender, prev_msg = semantic_history[idx - 1]
                if prev_msg not in used:
                    semantic_lines.append(f"[user]: {prev_msg}")
                    used.add(prev_msg)
                    semantic_lines.append(f"[assistant]: {msg}")
        if semantic_lines and len(semantic_lines) > 0:
            context_lines.append(
                f"  - Here are the {len(semantic_lines)//2} most relevant previous message exchanges:"
            )
            context_lines.extend(semantic_lines)
            context_lines.append("")
            context["middle_term_memory"] = semantic_lines

    # Knowledge Base Context - only if strategy allows and LLM is attached to KB
    if llm.is_attached_to_kb and (strategy["use_kb_basic"] or strategy["use_kb_enhanced"]):
        try:
            # Use enhanced KB retrieval with more chunks if strategy allows
            kb_top_k = strategy["kb_top_k"]
            kb_context = get_relevant_texts_if_kb(
                query=query, llm=llm, db=db
            )
            
            # Limit KB context based on strategy
            if kb_context:
                kb_context = kb_context[:kb_top_k]
            
            if not kb_context:
                logging.info("No relevant texts found in Knowledge Base")
            else:
                context_prefix = "\n\nAlso: You are attached to a Knowledge Base."
                if strategy["use_kb_enhanced"]:
                    context_prefix += " Here is detailed context you need to know for this query:\n"
                else:
                    context_prefix += " Here is basic context for this query:\n"
                
                context_lines.append(context_prefix + "\n".join(kb_context))
                context["kb_context"] = kb_context

        except Exception as e:
            logging.exception("Failed to retrieve Knowledge Base context")
            raise HTTPException(
                status_code=500, detail=f"Knowledge Base retrieval error: {str(e)}"
            )
    

    # Short-term memory (Recent messages) - only if strategy allows
    if strategy["use_short_term_memory"]:
        recent = conversation_history[-n_recent:] if len(conversation_history) >= n_recent else conversation_history
        if recent:
            context_lines.append(f"  - Here are the {len(recent)} most recent messages:")
            for sender, msg in recent:
                role = "[user]" if sender == "user" else "[assistant]"
                context_lines.append(f"{role}: {msg}")

    if context_lines and len(context_lines)>0:
        context["context_str"] = "Here is context about the conversation you had so far:\n\n" + "\n".join(context_lines)
    
    
    return context


@router.post("/conversations/{conversation_id}/generate_title")
async def generate_title(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):
    """Generate a title for the conversation based on the first message."""

    logging.info("Generating title for conversation %s", conversation_id)

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    model_type = llm.type
    global _loaded_model, _current_tokenizer, _loaded_model_id, _is_quant_on_current_load

    try:
        load_model(llm)
    except Exception as e:
        logging.exception("Failed to load model or tokenizer: %s", e)
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    try:
#         mistral_title_generation_prompt = f"""<|system|>You are a title generator. You must create VERY SHORT titles. No more than 5 words. Use only essential keywords. No articles (a, an, the). No punctuation.<|end|>

# <|user|>Create a 2-to-5-word title for: {payload.question}

# Examples:
# - How to cook pasta? → Pasta Cooking Guide
# - What is machine learning? → Machine Learning Basics
# - Help me with Python code → Python Code Help

# Your very short title:<|end|>
# <|assistant|>"""

        system_title_generation_prompt = f"""You are a title generator. You must create VERY SHORT titles. No more than 5 words. Use only essential keywords. No articles (a, an, the). No punctuation. Do NOT add any extra text, polite statements, or whatsoever. ONLY return the title.

Examples you need to follow:
- user: How to cook pasta? model: Pasta Cooking Guide
- user: What is machine learning? model: Machine Learning Basics

Now it's your turn. Keep it short, precise, and without any extra information 5 Words Max."""
        
        user_title_generation_prompt = f"""Create a 2-to-5-word title for:
{payload.question}"""
        # Merge system prompt into user message for models that don't support system role
        merged_title_prompt = f"{system_title_generation_prompt}\n\n{user_title_generation_prompt}"
        full_title_generation_prompt = [
            {"role": "user", "content": merged_title_prompt}
        ]
        prompt_tokens = _current_tokenizer.apply_chat_template(full_title_generation_prompt)
        sampler = mlx_lm.sample_utils.make_sampler(
            0.05,
            0.3,
            min_p=0.0,
            top_k=64,
            xtc_special_tokens=_current_tokenizer.encode("\n") + list(_current_tokenizer.eos_token_ids)
        )
    
    except Exception as e:
        logging.exception("Failed to tokenize prompt")
        raise HTTPException(status_code=500, detail=f"Tokenization error: {str(e)}")


    async def title_stream():
        generated_title = ""
        try:
            for new_text in mlx_lm.stream_generate(
                _loaded_model,
                _current_tokenizer,
                prompt_tokens,
                max_tokens=15,
                sampler=sampler,
                prompt_cache=None
            ):
                text = new_text.text
                if (
                    model_type == "mistral"
                    and text.strip() == ""
                    or "<" in text
                    or ">" in text
                    or "INST" in text
                    or "/" in text
                    or "[" in text
                    or "|" in text
                    or "end" in text
                    or "assistant" in text
                    or "system" in text
                    or "user" in text
                    or "title" in text
                    or "Your very short title" in text
                    or "Examples:" in text
                    or "Create a 2-to-5-word title for:" in text
                ) or (
                    model_type == "gemma"
                    and text.strip() == ""
                    or "<start_of" in text
                    or "bos" in text
                    or "eos" in text
                    or ">" in text
                    or "<" in text
                    or "<end_of" in text
                    or "_turn>" in text
                    or "assistant" in text
                    or "system" in text
                    or "user" in text
                    or "title" in text
                    or "Your very short title" in text
                    or "Examples:" in text
                    or "Create a 2-to-5-word title for:" in text
                ):
                    continue
                cleaned_token = text[0].upper() + text[1:]
                generated_title += cleaned_token
                logging.info(f"Yielding title token: {cleaned_token}")
                yield cleaned_token
        except Exception as e:
            logging.exception("Title streaming failed")
            raise HTTPException(status_code=500, detail="Title streaming failed")
        finally:
            # title_thread.join()
            words = generated_title.strip().split()
            if (
                '"' in words
                or "'" in words
                or "“" in words
                or "”" in words
                or "‘" in words
                or "’" in words
                or "«" in words
                or "»" in words
                or "title" in words
                or "your" in words
                or "here's" in words
                or "Okay" in words
                or "," in words
                or ":" in words
                or "`" in words
            ):
                words.remove('"')
                words.remove("'")
                words.remove("“")
                words.remove("”")
                words.remove("‘")
                words.remove("’")
                words.remove("«")
                words.remove("»")
                words.remove("title")
                words.remove("your")
                words.remove("here's")
                words.remove("Okay")
                words.remove(",")
                words.remove(":")
                words.remove("`")
            words = [re.sub(r"<.*?>", "", word) for word in words if word]
            final_title = " ".join(words[:6]) if len(words) >= 6 else " ".join(words)
            
            # Force lowercase except for first letter
            if final_title and len(final_title) > 0:
                final_title = final_title[0].upper() + final_title[1:].lower()

            conversation.name = final_title if (final_title and final_title.strip() != "") else "New Conversation"
            db.add(conversation)
            db.commit()
            logging.info("Title generated and saved: %s", conversation.name)

    return StreamingResponse(title_stream(), media_type="text/plain")


@router.post("/conversations/{conversation_id}/query")
async def query_and_respond(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):
    logging.info("Payload reçu : %s", payload.dict())
    user_prompt = payload.custom_prompt
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = Message(
        conversation_id=conversation_id, sender="user", content=payload.question
    )
    db.add(user_message)
    db.flush()

    conversation.last_message_time = datetime.now()
    db.commit()

    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    model_type = llm.type

    # Get prompting strategy based on model size
    param_size = llm.param_size if hasattr(llm, 'param_size') and llm.param_size else 2
    strategy = get_prompting_strategy(param_size)
    logging.info(f"Using prompting strategy for {param_size}B model: {strategy}")

    # Context Fetching
    try:
        full_msgs_history = get_conversation_history(db, conversation_id)
        if full_msgs_history[-1][0] == "user" :
            full_msgs_history.pop(-1)
        if not full_msgs_history or full_msgs_history == []:
            logging.info(
                "No previous messages in conversation, skipping context retrieval"
            )

        logging.info(f"Retrieving context for conversation {conversation_id}")
        start = datetime.now()
        context = retrieve_context(
            payload.question,
            full_msgs_history,
            conversation_id,
            llm=llm,
            db=db,
            strategy=strategy,
            top_k=payload.n_relevent_msgs_to_get or 3,
            n_last_turns=payload.n_last_turns_to_get or strategy["max_history_turns"],
            model_type=model_type,
        )
        context_str, long_term_memory, middle_term_memory, kb_context = context["context_str"], context["long_term_memory"], context["middle_term_memory"], context["kb_context"],

        messages_starred = []
        if full_msgs_history:
            for msg in full_msgs_history:
                msg_starred_object = (
                    db.query(Message)
                    .filter(Message.content == msg[1], Message.starred == True)
                    .first()
                )
                if msg_starred_object:
                    messages_starred.append(msg_starred_object.content)
            if len(messages_starred) == 0:
                messages_starred = None
    except Exception as e:
        logging.exception("Failed to retrieve context")
        raise HTTPException(
            status_code=500, detail=f"Context retrieval error: {str(e)}"
        )

    # Prompt construction - respects strategy
    # Separate components for strategic placement:
    # - System prompt: assistant's identity (goes at the beginning)
    # - Custom prompt: task-specific instructions (goes with current question)
    # - KB context: relevant knowledge (goes with current question)
    # - Long-term memory: conversation summary (goes at the beginning)
    
    sys_prompt = ""
    custom_prompt = ""
    kb_prompt = ""
    
    # System prompt: defines the assistant's identity (goes at the beginning)
    if strategy["use_system_prompt"]:
        sys_prompt = f"""You are {llm.name}, a concise and helpful assistant; answer directly in the user's tone without repeating context or mentioning instructions."""
    
    # Custom prompt: task-specific instructions (will be added to current question)
    if strategy["use_custom_prompt"] and payload.custom_prompt:
        custom_prompt = f"\nAdditional instructions: {payload.custom_prompt}"
    
    # KB context: relevant knowledge for the current query (will be added to current question)
    if kb_context and kb_context != "":
        kb_prompt = f"\nRelevant context from Knowledge Base:\n" + "\n".join(kb_context)
    
    # Long-term memory: conversation summary (goes at the beginning for overall context)
    if long_term_memory and long_term_memory != "":
        sys_prompt += f"\nSummary of the conversation you had so far: {long_term_memory}"
    
    final_prompt = []
    
    # Build conversation history - limited by strategy
    if len(full_msgs_history or []) > 0:
        # Use strategy's max_history_turns instead of hardcoded value
        # max_history_turns = number of conversation turns (each turn = user + assistant)
        max_turns = strategy["max_history_turns"]
        
        # Calculate how many messages to include (each turn = 2 messages)
        max_messages = max_turns * 2
        
        # Start from the last max_messages in history
        if len(full_msgs_history) > max_messages:
            start_idx = len(full_msgs_history) - max_messages
        else:
            start_idx = 0
        
        # Ensure we start on a user message (even index)
        if start_idx % 2 != 0:
            start_idx += 1
            
        logging.info(f"Including {max_turns} conversation turn(s) starting from index {start_idx}")
        logging.info(f"Total history length: {len(full_msgs_history)}, including from index {start_idx}")
        
        for i in range(start_idx, len(full_msgs_history), 2):
            if i < len(full_msgs_history):
                final_prompt.append({"role": "user", "content": full_msgs_history[i][1]})
            if i+1 < len(full_msgs_history):
                final_prompt.append({"role": "assistant", "content": full_msgs_history[i+1][1]})
    
    # Add current question with custom prompt and KB context fused into it
    current_question = payload.question
    
    # Build the current question with relevant context
    # Order: KB context (if any) -> Custom instructions (if any) -> Question
    question_with_context = ""
    
    if kb_prompt:
        question_with_context += kb_prompt + "\n\n"
    
    if custom_prompt:
        question_with_context += custom_prompt + "\n\n"
    
    question_with_context += payload.question
    current_question = question_with_context
    
    if len(final_prompt) == 0:
        # No history: merge system prompt into the first (and only) user message
        if sys_prompt:
            current_question = f"{sys_prompt}\n\n{current_question}"
    else:
        # Has history: prepend system prompt to first message in final_prompt
        if sys_prompt:
            final_prompt[0]["content"] = f"{sys_prompt}\n\n{final_prompt[0]['content']}"
    
    final_prompt.append({"role": "user", "content": current_question})
    logging.info("Final prompt to model:\n%s", final_prompt)

    # Model Loading
    try:
        load_model(llm)
    except Exception as e:
        logging.exception("Failed to load model or tokenizer")
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    try:
        prompt_tokens = _current_tokenizer.apply_chat_template(final_prompt)
        sampler = mlx_lm.sample_utils.make_sampler(
            payload.temperature,
            payload.top_p,
            min_p=0.0,
            top_k=64,
            xtc_special_tokens=_current_tokenizer.encode("\n") + list(_current_tokenizer.eos_token_ids)
        )
    except Exception as e:
        logging.exception("Failed to tokenize prompt")
        raise HTTPException(status_code=500, detail=f"Tokenization error: {str(e)}")


    async def assistant_response_token_stream():
        assistant_response = ""
        start = datetime.now()
        logging.info(f"Generating response from MLX model for prompt: {payload.question}")
        try:
            for new_text in mlx_lm.stream_generate(
                _loaded_model,
                _current_tokenizer,
                prompt_tokens,
                max_tokens=payload.max_new_tokens or 1024,
                sampler=sampler,
                prompt_cache=None
            ):
                
                text = new_text.text

                assistant_response += text
                logging.info(f"Yielding token: {text}")
                if text:
                    yield text

        except Exception as e:
            logging.exception("Streaming failed")
            error_msg = "[ERROR_MESSAGE_SYSTEM] Generation failed due to an error. Please try again or contact developer team."
            assistant_response = error_msg
            yield error_msg
            raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")
        finally:
            # Store the response (either successful or error message)
            assistant_message = Message(
                conversation_id=conversation_id,
                sender="llm",
                content=assistant_response.strip(),
            )
            db.add(assistant_message)
            conversation.last_message_time = datetime.now()
            db.commit()
            logging.info(f"Response generated in {datetime.now() - start} seconds")

            logging.info("Generation finished")
    
    return StreamingResponse(assistant_response_token_stream(), media_type="text/plain")


@router.post("/conversations/delete_bulk")
async def delete_bulk(
    payload: ConversationDeleteBulk,
    db: Session = Depends(get_db),
):
    """Delete multiple conversations by their IDs (body JSON)."""
    try:
        conversation_ids = payload.conversation_ids

        global _conversation_summary_cache
        for conv_id in conversation_ids:
            if conv_id in _conversation_summary_cache:
                del _conversation_summary_cache[conv_id]
                logging.info(
                    f"Cleared summary cache for deleted conversation {conv_id}"
                )

        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete conversations: {str(e)}",
        )
    return {"message": "Conversations deleted successfully"}


@router.post("/conversations/{conversation_id}/store_error_message")
async def store_error_message(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Store an error message in the conversation when generation fails."""

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Create an error message from the assistant
    error_message = Message(
        conversation_id=conversation_id,
        sender="llm",
        content="[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error while generating a response. Please try asking your question again.",
    )

    try:
        db.add(error_message)
        conversation.last_message_time = datetime.now()
        db.commit()

        logging.info(f"Stored error message for conversation {conversation_id}")
        global _loaded_model, _current_tokenizer
        if _loaded_model is not None:
            _loaded_model = None
            logging.info("Cleared model cache after error message storage")
        if _current_tokenizer is not None:
            _current_tokenizer = None
            logging.info("Cleared tokenizer cache after error message storage")
        return {
            "message": "Error message stored successfully",
            "error_message_id": error_message.id,
        }
    except Exception as e:
        db.rollback()
        logging.exception(
            f"Failed to store error message for conversation {conversation_id}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to store error message: {str(e)}"
        )


@router.post("/conversations/star_message")
async def star_message(
    message: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Star a message in the conversation."""

    message = db.query(Message).filter(Message.content == message).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message to star not found")

    message.starred = True
    try:
        db.commit()
        logging.info(f"Message {message.id} starred successfully.")
        return {"state": "success", "message": "Message starred successfully"}
    except Exception as e:
        db.rollback()
        logging.exception(f"Failed to star message.")
        raise HTTPException(status_code=500, detail=f"Failed to star message: {str(e)}")


@router.post("/conversations/unstar_message")
async def unstar_message(
    message: str = Body(..., embed=True),
    db: Session = Depends(get_db),
): 
    """Unstar a message in the conversation."""

    message = db.query(Message).filter(Message.content == message).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message to unstar not found")

    message.starred = False
    try:
        db.commit()
        logging.info(f"Message {message.id} unstarred successfully.")
        return {"state": "success", "message": "Message unstarred successfully"}
    except Exception as e:
        db.rollback()
        logging.exception(f"Failed to unstar message.")
        raise HTTPException(
            status_code=500, detail=f"Failed to unstar message: {str(e)}"
        )
