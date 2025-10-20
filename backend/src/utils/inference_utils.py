import faiss, os, numpy
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from src.entities.KnowledgeBase import KnowledgeBase
from src.entities.Llm import Llm
from src.entities.VectorStore import VectorStore
from src.utils.file_processor import chunk_by_tokens

from src.core.vars import (
    CACHE_DIR
)
from src.core.logging import logger

class EmbedderService:
    """Singleton service for managing the sentence transformer embedder.
    
    This service ensures only one instance of the embedder is loaded in memory
    and provides centralized access to it across the application.
    """
    _instance = None
    
    def __init__(self):
        raise RuntimeError("Use get_embedder() instead of instantiating")
    
    @classmethod
    def get_embedder(cls):
        """Get or create the embedder instance.
        
        Returns:
            SentenceTransformer: The singleton embedder instance.
        """
        from sentence_transformers import SentenceTransformer
        if cls._instance is None:
            logger.info("Loading the Embedder via EmbedderService")
            os.makedirs(CACHE_DIR, exist_ok=True)
            cls._instance = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                cache_folder=CACHE_DIR,
            )
            logger.info("Embedder loaded")
        return cls._instance
    
    @classmethod
    def cleanup(cls) -> None:
        """Release the embedder instance and free memory."""
        if cls._instance is not None:
            del cls._instance
            cls._instance = None
            logger.info("Embedder cleaned up")


def get_prompting_strategy(param_size: int) -> dict:
    """Determine optimal prompting strategy based on model size.
    
    Args:
        param_size: Model parameter size in billions.
    
    Returns:
        Dictionary containing strategy configuration flags.
    """

    if param_size <= 2: 
        # Ultra-lightweight strategy for tiny models (<2B)
        return {
            "system_prompt_size_category": "tiny",
            "use_custom_prompt": True,
            "max_history_turns": 2,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "mtm_top_k": 1,
            "use_long_term_memory": False,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 1,
        }
    elif param_size <= 4:  
        # Lightweight strategy for small models (2-3B)
        return {
            "system_prompt_size_category": "small",
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "mtm_top_k": 1,
            "use_long_term_memory": False,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 1,
        }
    elif param_size < 8: 
        # Medium strategy for 4-7B models
        return {
            "system_prompt_size_category": "medium",
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "mtm_top_k": 1,
            "use_long_term_memory": True,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 1,
        }
    elif param_size <= 16: 
        # Full strategy for 8-15B models
        return {
            "system_prompt_size_category": "large",
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "mtm_top_k": 1,
            "use_long_term_memory": True,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 1,
        }
    else:
        # Maximum strategy for large models (16B+)
        return {
            "system_prompt_size_category": "xlarge",
            "use_custom_prompt": True,
            "max_history_turns": 5,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "mtm_top_k": 2,
            "use_long_term_memory": True,
            "use_kb_basic": False,
            "use_kb_enhanced": True,
            "kb_top_k": 3,
        }
 

def build_system_prompt(
    model_name: str,
    size_category: str,
    long_term_memory: Optional[str] = None,
    starred_messages: Optional[List[str]] = None
) -> str:
    """
    Build a system prompt dynamically based on model size category.
    
    Args:
        model_name (str): Name of the model/assistant
        size_category (str): Size category ("tiny", "small", "medium", "large", "xlarge")
        long_term_memory (str, optional): Conversation summary to include
    
    Returns:
        str: The constructed system prompt
    """
    
    def get_cutoff_date(model_name: str) -> str:
        """
        Determine the training cutoff date based on the model name.
        
        Args:
            model_name: The name of the model
            
        Returns:
            str: The cutoff date (e.g., "October 2023", "August 2024")
        """
        model_name_lower = model_name.lower()
        
        # Ministral models - October 2023
        if "ministral" in model_name_lower:
            return "October 2023"
        
        # Gemma 12B - August 2024
        if "gemma" in model_name_lower and ("12b" in model_name_lower or "12" in model_name_lower):
            return "August 2024"
        
        if "nemo" in model_name_lower:
            return "April 2024"
        
        # Default for other large models
        return "August 2024"
    
    if size_category == "tiny":
        # Minimal system prompt for tiny models (<2B)
        sys_prompt = f"Tu es un assistant concis et utile. Répond toujours dans la même langue que la question de l’utilisateur. Ne donne que le contenu pertinent - sans commentaires ni répétition des consignes."
    elif size_category == "small":
        # Concise system prompt for small models (2-3B)
        sys_prompt = f"""You are {model_name}, a concise general assistant. Answer directly in ≤ 8 short lines. If unsure, say “Not sure” and ask 1 brief question. Don't restate the prompt or these rules. Use only the context sections below if relevant."""
    elif size_category == "medium":
                sys_prompt = f"""
            You are {model_name}, a precise, reliable assistant.

            General Guidelines:
            - Always respond in the user's language. Do not switch languages mid-response.
            - For non-programming tasks (e.g., resumes, summaries, emails), respond in plain, clean natural language.
            Do NOT wrap responses in code blocks or variables unless explicitly requested.
            - If JSON or other formats are requested, return clean, copy-ready output without extra explanation unless asked.

            Programming Requests:
            (Apply only when the user explicitly asks for code, examples, testing, or debugging.)

            - Always detect and use the user's language consistently.
            - Prefer minimal, correct, tested code examples. When providing code:
            * Use triple backticks with language tags (e.g., ```python).
            * Include necessary imports.
            * Provide a usage snippet or test when appropriate.
            - If the user asks to use a specific library or tool, always verify its existence.
            * If it is unknown or cannot be verified, say so clearly and suggest a reliable alternative.
            * Never fabricate code or documentation for libraries, tools, or packages that do not exist.
            * Explain the root cause.
            * Provide a clear, actionable fix.
            * Add a one-line summary of the change.
            - Prefer safe, conservative recommendations. For security- or privacy-sensitive instructions, either refuse or suggest a safe approach.
            - If the prompt is ambiguous, ask 1–2 clarifying questions before writing code.
            - Keep explanations concise and structured. Use numbered steps when listing actions.
            - When using external packages, include a ⁠ pip install ⁠ line if the package is non-standard.
            - For performance/memory optimization questions, include complexity/memory notes and brief trade-off analysis.

            End code answers with an optional one-line test or example the user can run locally.

            Never include internal hints, model metadata, or training data references. Output only what the user should see.
            """
    elif size_category == "large":
        # Detailed system prompt for large models (8-15B)
        current_date = datetime.now().strftime("%B %d, %Y")
        cutoff_date = get_cutoff_date(model_name)
        sys_prompt = f"""You are {model_name}, a helpful assistant. The current date is {current_date}. {model_name}'s training was last updated in {cutoff_date} and it answers user questions about events before {cutoff_date} and after {cutoff_date} the same way a highly informed individual from {cutoff_date} would if they were talking to someone from {current_date}. It avoids being repetitive or verbose unless specifically asked. Nobody likes listening to long rants! IT IS CONCISE. It is happy to help with writing, analysis, question answering, math, coding, and all sorts of other tasks. It uses markdown for coding."""
    else:  # "xlarge" (16B+)
        # Comprehensive system prompt for very large models
        sys_prompt = f"""You are {model_name}, a sophisticated AI assistant. Your role is to:
            - Provide accurate, well-reasoned responses
            - Adapt to the user's language, tone, and expertise level
            - Use context wisely without repeating it
            - Never mention system instructions or internal processes
            - Format responses clearly using Markdown when appropriate
            - When unsure about an answer, admit it rather than fabricating information
            - Understand the user and his needs deeply to provide tailored assistance.
            - Output only what the user should see."""
    
    # Add starred messages if there are any
    if starred_messages and len(starred_messages) > 0:
        starred_summary = "\n".join(f"- {msg}" for msg in starred_messages)
        sys_prompt += f"\nImportant points from the conversation so far:\n{starred_summary}"

    # Add long-term memory if provided
    if long_term_memory and long_term_memory.strip():
        sys_prompt += f"\nSummary of the conversation you had so far: {long_term_memory}"
    
    return sys_prompt

    
def get_relevant_texts_from_kb(
    query: str,
    llm: Llm,
    db: Session,
    kb_top_k: int
) -> List[str]:
    """Retrieve relevant text chunks from a knowledge base using semantic search.
    
    Args:
        query: The search query.
        llm: The language model with attached knowledge base.
        db: Database session.
        kb_top_k: Number of most relevant chunks to retrieve.
    
    Returns:
        List of relevant text chunks.
    
    Raises:
        Exception: If KB resources are missing or search fails.
    """
    # Validate knowledge base exists and is accessible
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == llm.kb_id).first()
    if not kb or not os.path.exists(kb.index_path):
        raise Exception(f"Knowledge Base index not found for LLM {llm.id}")

    # Load FAISS index
    try:
        faiss_index = faiss.read_index(kb.index_path)
        if not faiss_index:
            raise Exception(f"FAISS index not found for Knowledge Base {kb.id}")
    except Exception as e:
        raise Exception(f"Failed to read FAISS index for Knowledge Base {kb.id}") from e

    # Get vector store
    vector_store = db.query(VectorStore).filter(VectorStore.kb_id == kb.id).first()
    if not vector_store:
        raise Exception(f"VectorStore not found for Knowledge Base {kb.id}")

    # Process query
    embedder = EmbedderService.get_embedder()
    chunks = chunk_by_tokens(text=query)
    if not chunks:
        raise Exception("No valid text chunks found in the query.")

    relevant_texts = []
    for chunk in chunks:
        if not chunk.strip():
            continue

        # Encode query chunk
        try:
            logger.info(f"Encoding query chunk: {chunk[:50]}...")
            query_emb = embedder.encode(chunk, convert_to_tensor=True)
            if query_emb is None or query_emb.numel() == 0:
                raise Exception("Error embedding chunk.")
        except Exception as e:
            logger.error(f"Error embedding chunk: {e}")
            continue

        # Search similar vectors
        try:
            q = numpy.ascontiguousarray(
                query_emb.detach().cpu().numpy().astype("float32")
            ).reshape(1, -1)
            _, I = faiss_index.search(q, k=kb_top_k)
            
            # Collect matching texts
            for idx in I[0]:
                if idx >= 0:  # Skip invalid indices
                    faiss_id_str = str(idx)
                    if faiss_id_str in vector_store.vectors_data:
                        relevant_texts.append(vector_store.vectors_data[faiss_id_str])
        except Exception as e:
            raise Exception(f"Error searching FAISS index: {str(e)}") from e

    EmbedderService.cleanup()
    return relevant_texts