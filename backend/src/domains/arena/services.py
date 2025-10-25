"""Business logic for stateless arena LLM queries with KB-aware prompting.

This module orchestrates the complete query pipeline for arena testing:
1. **Prompt construction**: System prompt + KB context + custom instructions.
2. **Model loading**: Retrieve model/tokenizer via LLM_Engine.
3. **Streaming generation**: Yield tokens in real-time with configurable sampling.

Architecture:
    ┌──────────────┐
    │ ArenaService │
    │.query_llm_   │
    │ stream()     │
    └───────┬──────┘
            │ (1) Fetch LLM via ArenaRepository
            │ (2) Get prompting strategy (param_size-based)
            ↓
    ┌──────────────┐
    │_build_prompt │ ← build_system_prompt(size_category)
    │              │ ← _build_kb_context() if is_attached_to_kb
    │              │ ← payload.custom_prompt if provided
    └───────┬──────┘
            │ (3) Merge into single user message (stateless)
            ↓
    ┌──────────────┐
    │LLM_Engine    │ ← generate_stream(temp, top_p, max_tokens)
    │.generate_    │ → Yields tokens
    │ stream()     │
    └──────────────┘

Prompting Strategy:
    - Small models (<7B): Short system prompt, no KB, no custom prompt.
    - Medium models (7-13B): Medium system prompt, KB allowed, custom allowed.
    - Large models (>13B): Long system prompt, KB encouraged, custom encouraged.

KB Integration:
    - Uses get_relevant_texts_from_kb() to fetch top-k chunks via FAISS.
    - Injects as "Relevant context from Knowledge Base:" prefix.
    - Only enabled if llm.is_attached_to_kb=1 and strategy allows.

Example:
    from src.domains.arena.services import ArenaService
    from src.domains.arena.schemas import ArenaQueryPayload

    service = ArenaService(db)
    payload = ArenaQueryPayload(question="What is relativity?", temperature=0.7)
    async for token in service.query_llm_stream(llm_id=42, payload=payload):
        print(token, end="")
"""
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any

from src.core.logging import logger
from src.core import config
from src.utils.prompt_utils import get_prompting_strategy, build_system_prompt
from src.utils.kb_utils import get_relevant_texts_from_kb
from src.domains.arena.repository import ArenaRepository
from src.domains.arena.schemas import ArenaQueryPayload
from src.entities.Llm import Llm
from src.core.exceptions import (
    GenerationException,
    KnowledgeBaseNotFoundException,
    KnowledgeBaseCorruptedException,
    ModelNotFoundException,
    InvalidInputException,
    ModelLoadingException,
)


class ArenaService:
    """Service layer for arena stateless query processing."""
    
    def __init__(self, db):
        """Initialize arena service with database session.

        Args:
            db: SQLAlchemy database session for repository access.
        """
        logger.debug("Initializing ArenaService")
        self.arena_repo = ArenaRepository(db)
        self.db = db

    def _get_llm(self, llm_id: int) -> Llm:
        """Retrieve LLM entity by ID via repository.

        Args:
            llm_id: Database primary key of the LLM.

        Returns:
            Llm entity with metadata (name, link, param_size, is_attached_to_kb).

        Raises:
            HTTPException: 404 if LLM not found (raised by repository).
        """
        return self.arena_repo.get_llm_by_id(llm_id)

    def _build_kb_context(
        self,
        llm: Llm,
        query: str,
        strategy: Dict[str, Any]
    ) -> str:
        """Build Knowledge Base context string if LLM has KB attached and strategy allows.

        Queries FAISS index for top-k relevant chunks, formats as context string. Only
        executes if llm.is_attached_to_kb=1 and strategy["use_kb_context"]=True.

        Args:
            llm: LLM entity with potential KB attachment (kb_id foreign key).
            query: User question to search KB for relevant chunks.
            strategy: Prompting strategy dict with use_kb_context and kb_top_k settings.

        Returns:
            Formatted KB context string ("Relevant context from Knowledge Base:\\n..."),
            or empty string if KB not available/disabled.

        Raises:
            AppBaseException: If KB retrieval fails (FAISS error, embedder error).

        Example:
            >>> context = service._build_kb_context(llm, "What is GPU?", strategy)
            >>> print(context)
            "Relevant context from Knowledge Base:\\nGPU stands for Graphics Processing Unit..."
        """
        if not llm.is_attached_to_kb or not strategy.get("use_kb_context", False):
            return ""
        
        try:
            relevant_texts = get_relevant_texts_from_kb(
                query, llm, self.db, kb_top_k=strategy.get("kb_top_k", 1)
            )
            if relevant_texts:
                return "Relevant context from Knowledge Base:\n" + "\n".join(relevant_texts)
        except (KnowledgeBaseNotFoundException, KnowledgeBaseCorruptedException):
            raise
        except Exception as e:
            logger.exception("Failed to retrieve Knowledge Base context")
            raise KnowledgeBaseCorruptedException(
                llm.kb_id,
                f"Knowledge Base retrieval error: {e}",
                trace=str(e)
            )
        
        return ""

    def _build_prompt(
        self,
        llm: Llm,
        payload: ArenaQueryPayload,
        strategy: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Build final prompt with system instructions, KB context, and custom additions.

        Assembles the complete prompt from multiple sources:
        1. System prompt (size_category-based: small/medium/large).
        2. KB context (if is_attached_to_kb and strategy allows).
        3. Custom prompt (if strategy allows and payload provides).
        4. User question.

        All components merged into single user message (arena is stateless, no history).

        Args:
            llm: LLM entity with param_size and is_attached_to_kb metadata.
            payload: Query payload with question and optional custom_prompt.
            strategy: Prompting strategy dict with flags and settings.

        Returns:
            List with single message dict: [{"role": "user", "content": "..."}]

        Example:
            >>> prompt = service._build_prompt(llm, payload, strategy)
            >>> print(prompt)
            [{"role": "user", "content": "You are a helpful assistant...\\n\\nRelevant context...\\n\\nWhat is AI?"}]
        """
        # Build system prompt
        size_category = strategy.get("system_prompt_size_category", "medium")
        sys_prompt = build_system_prompt(
            model_name=llm.name,
            size_category=size_category,
            long_term_memory=None,
            starred_messages=None
        )

        # Build KB context if applicable
        kb_prompt = self._build_kb_context(llm, payload.question, strategy)

        # Build custom prompt addition if applicable
        custom_prompt = ""
        if strategy.get("use_custom_prompt", False) and payload.custom_prompt:
            custom_prompt = f"\nAdditional instructions: {payload.custom_prompt}"

        # Assemble the current question with all context
        question_with_context = ""
        
        if kb_prompt:
            question_with_context += kb_prompt + "\n\n"
        
        if custom_prompt:
            question_with_context += custom_prompt + "\n\n"
        
        question_with_context += payload.question

        # Merge system prompt into first user message (stateless arena has no history)
        if sys_prompt:
            question_with_context = f"{sys_prompt}\n\n{question_with_context}"

        final_prompt = [{"role": "user", "content": question_with_context}]
        
        logger.info("Final prompt to model:\n%s", final_prompt)
        return final_prompt

    async def query_llm_stream(
        self,
        llm_id: int,
        payload: ArenaQueryPayload
    ) -> AsyncGenerator[str, None]:
        """Query LLM in stateless arena mode and stream response tokens.

        Complete query pipeline:
        1. Validate question non-empty.
        2. Fetch LLM from database.
        3. Determine prompting strategy based on param_size.
        4. Build final prompt (system + KB + custom + question).
        5. Load model/tokenizer via LLM_Engine.
        6. Generate stream with configured sampling parameters.
        7. Yield tokens in real-time.

        Args:
            llm_id: Database ID of the LLM to query.
            payload: Query request with question and generation parameters.

        Yields:
            Text tokens from model generation (incremental, not cumulative).

        Raises:
            AppBaseException: If question empty, model loading fails, or generation fails.

        Example:
            >>> service = ArenaService(db)
            >>> payload = ArenaQueryPayload(question="What is AI?", temperature=0.7)
            >>> async for token in service.query_llm_stream(42, payload):
            ...     print(token, end="", flush=True)
            "Artificial Intelligence is..."
        """
        # Validate question
        if not payload.question or not payload.question.strip():
            raise InvalidInputException("question")

        # Get LLM from database
        logger.info(f"Querying LLM {llm_id} from DB")
        llm = self._get_llm(llm_id)
        logger.info(f"Retrieved LLM: {llm.name}")

        # Get prompting strategy based on model size
        param_size = llm.param_size if hasattr(llm, 'param_size') and llm.param_size else 2
        strategy = get_prompting_strategy(param_size)
        logger.info(f"Using prompting strategy for {param_size}B model: {strategy}")

        # Build final prompt
        final_prompt = self._build_prompt(llm, payload, strategy)

        # Load model and tokenizer
        try:
            model, tokenizer = config.LLM_Engine.get_model_and_tokenizer(
                llm_id=llm.id,
                llm_local_path=llm.link
            )
        except Exception as e:
            logger.exception("Failed to load model or tokenizer")
            raise ModelLoadingException(
                model_path=llm.link,
                trace=e
            )

        # Generate response stream
        assistant_response = ""
        start = datetime.now()
        logger.info(f"Generating response for prompt: {payload.question}")
        
        try:
            for new_text in config.LLM_Engine.generate_stream(
                model=model,
                tokenizer=tokenizer,
                prompt=final_prompt,
                max_tokens=payload.max_new_tokens or 1024,
                temperature=payload.temperature or 0.1,
                top_p=payload.top_p or 0.5,
                repetition_penalty=1.2,
                repetition_context_size=payload.max_new_tokens or 1024,
            ):
                assistant_response += new_text
                if new_text:
                    yield new_text
        except Exception as e:
            logger.exception("Streaming failed")
            raise GenerationException(
                message="Streaming failed during generation",
                trace=e
            )
        finally:
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(
                f"Generation completed in {elapsed:.2f}s. "
                f"Response length: {len(assistant_response)} chars"
            )
