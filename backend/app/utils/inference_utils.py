import mlx_lm
import logging
import faiss
import os
import torch
import threading
import asyncio
import gc
import numpy as np
from sentence_transformers import SentenceTransformer
from datetime import datetime, timedelta
from typing import Optional, Tuple, Any, List, Callable

from sqlalchemy.orm import Session

from app.models.KnowledgeBase import KnowledgeBase
from app.models.Llm import Llm
from app.models.VectorStore import VectorStore
from app.utils.file_processor import chunk_by_tokens
from app.utils.path_utils import get_cache_dir

CACHE_DIR = str(get_cache_dir())

class ModelManager:
    """Singleton manager for MLX models and tokenizers.
    
    Handles loading, caching, cleanup, and inference for models while ensuring
    thread-safety and memory efficiency. Models are automatically
    cleaned up after a period of inactivity.
    """
    _instance: Optional[Any] = None
    _tokenizer: Optional[Any] = None
    _model_id: Optional[int] = None
    _last_used: Optional[datetime] = None
    _lock = threading.Lock()
    _cleanup_task = None
    _max_idle_time = 300  # 5 minutes
    
    def __init__(self):
        raise RuntimeError("Use the methods instead of instantiating")

    @classmethod
    def generate_stream(
        cls,
        model: Any,
        tokenizer: Any,
        prompt: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
        top_p: float = 0.5,
        top_k: int = 64,
        repetition_penalty: Optional[float] = None,
        repetition_context_size: Optional[int] = 1024,
        min_p: float = 0.0,
    ):
        """Generate streaming response from the model.
        
        Args:
            model: The loaded MLX model.
            tokenizer: The tokenizer associated with the model.
            prompt: List of dictionaries with 'role' and 'content' keys
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling probability threshold
            top_k: Top-k sampling threshold
            repetition_penalty: Penalty for repeating tokens
            repetition_context_size: Number of past tokens to consider for repetition
            min_p: Minimum probability for nucleus sampling
            
        Yields:
            Generated text tokens
        
        Raises:
            Exception: If model loading or generation fails
        """
        with cls._lock:
            try:
                # Tokenize prompt
                prompt_tokens = tokenizer.apply_chat_template(prompt, add_generation_prompt=True)
                eos_ids = list(tokenizer.eos_token_ids)

                # Create sampler
                sampler = mlx_lm.sample_utils.make_sampler(
                    temperature,
                    top_p,
                    min_p=min_p,
                    top_k=top_k,
                )  # Rayan - Ne pas remettre xtc_special_tokens car ce n'est pas consommé, cf https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/sample_utils.py

                # Build logits processors
                logits_processors = mlx_lm.sample_utils.make_logits_processors(
                repetition_penalty=repetition_penalty,
                repetition_context_size=repetition_context_size,
            )

                # Generate stream
                text = ""
                logging.info("=" * 10)
                for response in mlx_lm.stream_generate(
                    model,
                    tokenizer,
                    prompt_tokens,
                    max_tokens=max_tokens,
                    sampler=sampler,
                    logits_processors=logits_processors if logits_processors != [] else None,
                    prompt_cache=None
                ):  
                    if response:
                        # logging.debug(f"Yielding new chunk:\n{new_text.__repr__()}")
                        token_repr = response.text.replace('\n', '\\n').replace('\t', '\\t')
                        logging.info(f"Yielding token: {token_repr}")
                        text += response.text
                        yield response.text

                logging.info("=" * 10)

                if len(text) == 0:
                    logging.info("No text generated for this prompt")
                
                logging.info(f"Generation: {response.generation_tokens} tokens")
                logging.info(f"{response.generation_tps:.3f} tokens-per-sec")
                logging.info(f"Peak memory: {response.peak_memory:.3f} GB")

                cls._last_used = datetime.now()  # Update last use time
            except Exception as e:
                logging.exception("Generation failed")
                raise Exception(f"Generation error: {str(e)}")
    
    @classmethod
    def _build_logits_processors(
        cls,
        repetition_penalty: Optional[float] = None,
        repetition_context_size: Optional[int] = 1024,
    ) -> List[Callable]:
        """Build a list of logit processors for controlling text generation.
        
        Args:
            repetition_penalty: Penalty factor for token repetition.
            repetition_context_size: Number of past tokens to consider for repetition.
        
        Returns:
            List of logit processor functions.
        """

        # --- Build logits_processors (keep repetition_penalty) and append our min_new_tokens processor ---
        logits_processors = []
        if repetition_penalty is not None and repetition_penalty > 1.0:
            logits_processors = mlx_lm.sample_utils.make_logits_processors(
                repetition_penalty=repetition_penalty,
                repetition_context_size=repetition_context_size,
            )
            
        return logits_processors

    @classmethod
    def get_model(cls, llm: Llm) -> Tuple[Any, Any]:
        """Get or load a model and its tokenizer.
        
        Args:
            llm: The LLM model to load.
            
        Returns:
            Tuple of (model, tokenizer).
            
        Thread-safe and ensures only one copy of the model exists.
        """
        with cls._lock:
            if llm.id == cls._model_id and cls._instance is not None and cls._tokenizer is not None:
                cls._last_used = datetime.now()
                logging.info(f"Using cached model {llm.id}")
                return cls._instance, cls._tokenizer
            
            # Need to load new model
            logging.info(f"Loading new model {llm.id}, cleaning up old model ({cls._model_id}) if exists")
            cls.cleanup()  # Clean old model if exists
            cls._load_model(llm)
            cls._last_used = datetime.now()
            return cls._instance, cls._tokenizer
    
    @classmethod
    def _load_model(cls, llm: Llm) -> None:
        """Internal method to load a model and its tokenizer.
        
        Args:
            llm: The LLM model to load.
        """
        logging.info(f"Loading MLX model and tokenizer for {llm.id}...")
        start = datetime.now()
        try:
            cls._instance, cls._tokenizer = mlx_lm.load(llm.link)
            cls._model_id = llm.id
            logging.info(f"Model and tokenizer loaded in {datetime.now() - start}")
        except Exception as e:
            cls._instance = None
            cls._tokenizer = None
            cls._model_id = None
            logging.error(f"Failed to load model: {e}")
            raise
    
    @classmethod
    def cleanup(cls) -> None:
        """Clean up the current model and free memory."""
        if cls._instance is not None or cls._tokenizer is not None:
            logging.info(f"Cleaning up model {cls._model_id}")
            cls._instance = None
            cls._tokenizer = None
            cls._model_id = None
            cls._last_used = None
            
            # Clean CUDA/MPS memory if available
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
                torch.mps.synchronize()
            gc.collect()
    
    @classmethod
    def _should_cleanup(cls) -> bool:
        """Check if the model should be cleaned up based on idle time."""
        logging.info("Checking if model should be cleaned up...")
        if cls._last_used is None or cls._instance is None:
            logging.info("No model loaded, no cleanup needed")
            return False
        
        idle_time = datetime.now() - cls._last_used
        should_cleanup = idle_time > timedelta(seconds=cls._max_idle_time)
        logging.info(f"Model idle for {idle_time}, should cleanup: {should_cleanup}")
        return should_cleanup
    
    @classmethod
    async def _cleanup_monitor(cls) -> None:
        """Background task that monitors for idle models and cleans them up."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            with cls._lock:
                logging.info("Running model cleanup monitor...")
                if cls._should_cleanup():
                    logging.info("Cleaning up idle model")
                    cls.cleanup()
    
    @classmethod
    def start_cleanup_task(cls) -> None:
        """Start the background cleanup task.
        
        Should be called once when the application starts.
        """
        if cls._cleanup_task is None:
            cls._cleanup_task = asyncio.create_task(cls._cleanup_monitor())
            logging.info("Started model cleanup monitor")
    
    @classmethod
    def stop_cleanup_task(cls) -> None:
        """Stop the background cleanup task.
        
        Should be called when the application shuts down.
        """
        if cls._cleanup_task is not None:
            cls._cleanup_task.cancel()
            cls._cleanup_task = None
            logging.info("Stopped model cleanup monitor")
        else:
            logging.info("Cleanup monitor was not running")


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
        if cls._instance is None:
            logging.info("Loading the Embedder via EmbedderService")
            os.makedirs(CACHE_DIR, exist_ok=True)
            cls._instance = SentenceTransformer(
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                cache_folder=CACHE_DIR,
            )
            logging.info("Embedder loaded")
        return cls._instance
    
    @classmethod
    def cleanup(cls) -> None:
        """Release the embedder instance and free memory."""
        if cls._instance is not None:
            del cls._instance
            cls._instance = None
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            logging.info("Embedder cleaned up")


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
        sys_prompt = f"You are a concise and helpful assistant. Always respond in the same language as the user's question. Provide only the relevant content - no commentary or repetition of the instructions."
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
            logging.info(f"Encoding query chunk: {chunk[:50]}...")
            query_emb = embedder.encode(chunk, convert_to_tensor=True)
            if query_emb is None or query_emb.numel() == 0:
                raise Exception("Error embedding chunk.")
        except Exception as e:
            logging.error(f"Error embedding chunk: {e}")
            continue

        # Search similar vectors
        try:
            q = np.ascontiguousarray(
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