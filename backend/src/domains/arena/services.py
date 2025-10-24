"""
Services for arena domain.
All business logic resides here. No direct database access.
"""
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any

from src.core.logging import logger
from backend.src.core import config
from src.utils.prompt_utils import get_prompting_strategy, build_system_prompt
from src.utils.kb_utils import get_relevant_texts_from_kb
from src.domains.arena.repository import ArenaRepository
from src.domains.arena.schemas import ArenaQueryPayload
from src.entities.Llm import Llm
from src.core.exceptions import AppBaseException


class ArenaService:
    """Service for managing arena query processing."""
    
    def __init__(self, db):
        """
        Initialize the arena service.
        
        Args:
            db: Database session
        """
        logger.debug("Initializing ArenaService")
        self.arena_repo = ArenaRepository(db)
        self.db = db

    def _get_llm(self, llm_id: int) -> Llm:
        """
        Retrieve LLM by ID.
        
        Args:
            llm_id: ID of the LLM
            
        Returns:
            The Llm object
        """
        return self.arena_repo.get_llm_by_id(llm_id)

    def _build_kb_context(
        self,
        llm: Llm,
        query: str,
        strategy: Dict[str, Any]
    ) -> str:
        """
        Build knowledge base context if available and strategy allows.
        
        Args:
            llm: The LLM with potential KB attachment
            query: The user query
            strategy: Prompting strategy configuration
            
        Returns:
            Formatted KB context string or empty string
        """
        if not llm.is_attached_to_kb or not strategy.get("use_kb_context", False):
            return ""
        
        try:
            relevant_texts = get_relevant_texts_from_kb(
                query, llm, self.db, kb_top_k=strategy.get("kb_top_k", 1)
            )
            if relevant_texts:
                return "Relevant context from Knowledge Base:\n" + "\n".join(relevant_texts)
        except Exception as e:
            logger.exception("Failed to retrieve Knowledge Base context")
            raise AppBaseException(
                message="Knowledge Base retrieval error",
                trace=e
            )
        
        return ""

    def _build_prompt(
        self,
        llm: Llm,
        payload: ArenaQueryPayload,
        strategy: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Build the final prompt for the model.
        
        Args:
            llm: The LLM being queried
            payload: The query payload
            strategy: Prompting strategy configuration
            
        Returns:
            List of message dictionaries for the model
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
        """
        Query an LLM in the arena and stream the response.
        
        Args:
            llm_id: ID of the LLM to query
            payload: The query payload with question and parameters
            
        Yields:
            Text tokens from the model response
            
        Raises:
            AppBaseException: If model loading or generation fails
        """
        # Validate question
        if not payload.question or not payload.question.strip():
            raise AppBaseException(message="Question cannot be empty")

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
            raise AppBaseException(
                message="Model loading error",
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
            raise AppBaseException(
                message="Streaming failed",
                trace=e
            )
        finally:
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(
                f"Generation completed in {elapsed:.2f}s. "
                f"Response length: {len(assistant_response)} chars"
            )
