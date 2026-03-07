"""Services for conversation management and streaming AI generation.

This module contains business logic for:
- Conversation lifecycle (create, update, delete)
- Streaming token generation with LLM engines
- Message persistence and history management
- Context window optimization and caching
- RAG integration (knowledge base injection)
- Title auto-generation from first message

Architecture:
    Service Layer Pattern:
    ┌────────────────────────────────────────────────────────────┐
    │ ConversationService                                        │
    │  - Business logic and orchestration                        │
    │  - Uses repositories for data access                       │
    │  - Uses engine for LLM inference                           │
    └────────────────────────────────────────────────────────────┘
                            ↓
    ┌────────────────────────────────────────────────────────────┐
    │ ConversationRepository / MessageRepository                 │
    │  - Database CRUD operations                                │
    │  - No business logic                                       │
    └────────────────────────────────────────────────────────────┘

Key Methods:
    - create_conversation(): Initialize new chat session
    - query_and_respond_stream(): Stream AI response token-by-token
    - generate_title_stream(): Auto-generate conversation title
    - delete_conversation(): Remove conversation with cascade
    - store_error_message(): Record generation failures

Context Management:
    - ConversationCache: In-memory cache for recent conversations
    - ConversationContext: Context window optimization (last N turns)
    - System prompt injection via prompt_utils

Example:
    Stream AI response to user query::

        service = ConversationService(db)
        
        async for token in service.query_and_respond_stream(
            conversation_id=42,
            payload=ConversationQuery(question="Explain Python decorators")
        ):
            print(token, end="", flush=True)

Note:
    All streaming methods are async generators (AsyncGenerator[str, None]).
    Message persistence happens AFTER streaming completes.

Warning:
    Service methods are NOT thread-safe. Create new service instance per request.
"""

"""
Services for managing conversations and message processing.
All business logic resides here. No direct database access.
"""
from typing import List, Tuple, Optional, Generator

from src.core.logging import logger
from src.core import config
from src.utils.prompt_utils import get_prompting_strategy, build_system_prompt
from src.domains.conversations.repository import ConversationRepository, MessageRepository
from src.domains.conversations.utils.cache import ConversationCache
from src.domains.conversations.utils.context import ConversationContext
from src.domains.conversations.schemas import ConversationQuery
from src.entities.Conversation import Conversation
from src.entities.Message import Message


class ConversationService:
    """Service for managing conversations and message processing."""
    
    def __init__(self, db):
        """Initialize the conversation service with database session and utilities.

        Args:
            db: SQLAlchemy database session for repository operations.

        Note:
            Creates repository instances, conversation cache, and context manager.
        """
        """
        Initialize the conversation service.
        
        Args:
            db: Database session
        """
        logger.debug("Initializing ConversationService")
        self.conversation_repo = ConversationRepository(db)
        self.message_repo = MessageRepository(db)
        self.cache = ConversationCache()
        self.context_manager = ConversationContext()
        self.db = db

    def create_conversation(
        self,
        llm_id: int,
        temperature: float = 0.2,
        top_p: float = 0.5,
        max_tokens: int = 1024,
        custom_prompt: str = ""
    ) -> Conversation:
        """Create a new conversation with specified LLM and generation parameters.

        Args:
            llm_id: ID of the LLM model to use for this conversation.
            temperature: Sampling temperature (0.0-2.0, default 0.2).
            top_p: Nucleus sampling threshold (0.0-1.0, default 0.5).
            max_tokens: Maximum tokens to generate (1-32768, default 1024).
            custom_prompt: Custom system prompt override (optional).

        Returns:
            Conversation: Created conversation object with auto-generated name.

        Example:
            ::

                service = ConversationService(db)
                conv = service.create_conversation(
                    llm_id=5,
                    temperature=0.7,
                    custom_prompt="You are a Python expert."
                )
        """
        """
        Create a new conversation.
        
        Args:
            llm_id: ID of the LLM to use
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            max_tokens: Maximum tokens to generate
            custom_prompt: Custom system prompt
            
        Returns:
            The created Conversation object
        """
        logger.info(f"Creating new conversation with LLM {llm_id}")
        return self.conversation_repo.create_conversation(
            llm_id=llm_id,
            name="New Conversation",
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            custom_prompt=custom_prompt
        )

    def update_conversation(
        self,
        conversation_id: int,
        name: Optional[str] = None,
        llm_id: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        custom_prompt: Optional[str] = None
    ) -> Conversation:
        """Update conversation metadata (partial update with optional fields).

        Args:
            conversation_id: ID of the conversation to update.
            name: Optional new name for the conversation.
            llm_id: Optional new LLM ID.
            temperature: Optional new temperature.
            top_p: Optional new top_p.
            max_tokens: Optional new max_tokens.
            custom_prompt: Optional new system prompt.

        Returns:
            Conversation: Updated conversation object.

        Note:
            Only provided (non-None) fields are updated. Omitted fields remain unchanged.
        """
        """
        Update conversation fields.
        
        Args:
            conversation_id: ID of the conversation to update
            name: New name for the conversation
            llm_id: New LLM ID
            temperature: New temperature
            top_p: New top_p
            max_tokens: New max_tokens
            custom_prompt: New custom prompt
            
        Returns:
            Updated Conversation object
        """
        logger.info(f"Updating conversation {conversation_id}")
        return self.conversation_repo.update_conversation(
            conversation_id=conversation_id,
            name=name,
            llm_id=llm_id,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            custom_prompt=custom_prompt
        )

    def delete_conversation(self, conversation_id: int) -> None:
        """Delete a conversation, its messages, and clear cache (cascade delete).

        Args:
            conversation_id: ID of the conversation to delete.

        Returns:
            None.

        Note:
            Cache is cleared before database deletion to ensure consistency.
            All messages are also deleted due to cascade constraints.
        """
        """
        Delete a conversation and clear its cache.
        
        Args:
            conversation_id: ID of the conversation to delete
        """
        logger.info(f"Deleting conversation {conversation_id}")
        
        # Clear cache first
        self.cache.remove_conversation_cache(conversation_id)
        
        # Delete from database
        self.conversation_repo.delete_conversation(conversation_id)

    def delete_conversations_bulk(self, conversation_ids: List[int]) -> None:
        """Delete multiple conversations in a single operation (bulk delete).

        Args:
            conversation_ids: List of conversation IDs to delete.

        Returns:
            None.

        Note:
            Clears cache for all conversations before database deletion.
            More efficient than deleting one-by-one.
        """
        """
        Delete multiple conversations and clear their caches.
        
        Args:
            conversation_ids: List of conversation IDs to delete
        """
        logger.info(f"Bulk deleting {len(conversation_ids)} conversations")
        
        # Clear caches
        self.cache.bulk_remove_conversations(conversation_ids)
        
        # Delete from database
        self.conversation_repo.delete_conversations_bulk(conversation_ids)

    def store_error_message(self, conversation_id: int) -> int:
        """Store an error message when AI generation fails (fallback mechanism).

        Args:
            conversation_id: ID of the conversation where error occurred.

        Returns:
            int: ID of the created error message.

        Note:
            Used by frontend to record generation failures and maintain
            conversation history consistency.
        """
        """
        Store an error message when generation fails.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            ID of the created error message
        """
        logger.info(f"Storing error message for conversation {conversation_id}")
        
        error_content = (
            "[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error "
            "while generating a response. Please try asking your question again."
        )
        
        message = self.message_repo.create_message(
            conversation_id=conversation_id,
            content=error_content,
            sender="llm",
        )
        
        # Update conversation timestamp
        self.conversation_repo.update_last_message_time(conversation_id)
        
        # Cleanup engine
        config.LLM_Engine.cleanup()
        
        return message.id

    def generate_title_stream(
        self,
        conversation_id: int,
        question: str
    ) -> Generator[str, None, None]:
        """Generate a title for the conversation based on the first message.

        Sync generator — Starlette runs each ``next()`` call in a threadpool
        and flushes the yielded chunk to the HTTP response immediately.

        Args:
            conversation_id: ID of the conversation.
            question: The user's question to base the title on.

        Yields:
            Title text chunks.
        """
        logger.info(f"Generating title for conversation {conversation_id}")

        # Get conversation and LLM
        conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
        llm = self.conversation_repo.get_llm_by_id(conversation.llm_id)

        # Early return if question is empty
        if not question or question.strip() == "":
            conversation.name = "New Conversation"
            self.db.commit()
            return

        # Load model
        model, tokenizer = config.LLM_Engine.get_model_and_tokenizer(
            llm_id=llm.id,
            llm_local_path=llm.link
        )

        # Build title generation prompt
        prompt = self._build_title_prompt(question, llm.type)

        # Generate title
        generated_title = ""
        temp = 0.5 if llm.type == "mistral" else 1.0
        nucleus = 0.9 if llm.type == "mistral" else 0.95
        max_tok = 12

        try:
            for new_text in config.LLM_Engine.generate_stream(
                model=model,
                tokenizer=tokenizer,
                prompt=prompt,
                temperature=temp,
                top_p=nucleus,
                max_tokens=max_tok,
                repetition_penalty=1.2,
            ):
                logger.debug(f"[TitleGen Stream] token: {new_text}")
                generated_title += new_text
                yield new_text
        except Exception as e:
            logger.exception("Title streaming failed")
        finally:
            # Save the generated title
            final_title = generated_title if generated_title else "New Conversation"
            conversation.name = final_title
            self.db.commit()
            logger.info(f"Title generated and saved: {conversation.name}")

    def query_and_respond_stream(
        self,
        conversation_id: int,
        payload: ConversationQuery
    ) -> Generator[str, None, None]:
        """Process a query and stream the response token-by-token.

        Sync generator — Starlette runs each ``next()`` call in a threadpool
        and flushes the yielded chunk to the HTTP response immediately,
        enabling real-time token streaming to the frontend.

        Args:
            conversation_id: ID of the conversation.
            payload: Query payload with question and parameters.

        Yields:
            Response text chunks (individual tokens).
        """
        logger.info(f"Processing query for conversation {conversation_id}")

        # Get conversation and LLM
        conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
        llm = self.conversation_repo.get_llm_by_id(conversation.llm_id)

        # Store user message
        user_message = self.message_repo.create_message(
            conversation_id=conversation_id,
            sender="user",
            content=payload.question
        )

        # Update conversation timestamp
        self.conversation_repo.update_last_message_time(conversation_id)

        # Commit user message immediately so it's visible
        self.db.commit()

        # Get prompting strategy
        strategy = get_prompting_strategy(llm.param_size)
        logger.info(f"Using prompting strategy for {llm.param_size}B model: {strategy}")

        # Get conversation history (excluding the just-added user message)
        full_history = self.message_repo.get_conversation_history(conversation_id)
        if full_history and full_history[-1][0] == "user":
            full_history = full_history[:-1]

        # Retrieve context
        context = self.context_manager.retrieve_context(
            query=payload.question,
            conversation_history=full_history,
            conversation_id=conversation_id,
            llm=llm,
            db=self.db,
            strategy=strategy,
            n_last_turns=payload.n_last_turns_to_get or strategy["max_history_turns"],
            model_type=llm.type
        )

        # Get starred messages
        starred_messages = self.message_repo.get_starred_messages(conversation_id)

        # Build prompt
        final_prompt = self._build_query_prompt(
            question=payload.question,
            history=full_history,
            context=context,
            starred_messages=starred_messages,
            llm=llm,
            strategy=strategy,
            custom_prompt=payload.custom_prompt
        )

        # Load model
        model, tokenizer = config.LLM_Engine.get_model_and_tokenizer(
            llm_id=llm.id,
            llm_local_path=llm.link
        )

        # Generate response
        assistant_response = ""
        try:
            for text in config.LLM_Engine.generate_stream(
                model=model,
                tokenizer=tokenizer,
                prompt=final_prompt,
                max_tokens=payload.max_new_tokens or 1024,
                temperature=payload.temperature,
                top_p=payload.top_p,
                repetition_penalty=1.2,
                repetition_context_size=payload.max_new_tokens or 1024,
            ):
                assistant_response += text
                yield text
        except Exception as e:
            logger.exception("Streaming failed")
            error_msg = (
                "[ERROR_MESSAGE_SYSTEM] Generation failed due to an error. "
                "Please try again or contact developer team."
            )
            assistant_response = error_msg
            yield error_msg
        finally:
            # Store assistant response
            self.message_repo.create_message(
                conversation_id=conversation_id,
                sender="llm",
                content=assistant_response.strip()
            )

            # Update conversation timestamp
            self.conversation_repo.update_last_message_time(conversation_id)

            # Commit all changes (user message + assistant message + timestamp)
            self.db.commit()

    def _build_title_prompt(self, question: str, model_type: str) -> List[dict]:
        """Build prompt for title generation."""
        if model_type == "mistral":
            prompt = (
                "You are a TITLE generator. Produce ONLY a very short title "
                "(2–4 words maximum).\n"
                "Rules: only the title text; Title Case; no question mark; "
                "no quotes; no emojis; no hashtags; no code; no trailing "
                "punctuation; never answer the question; if empty/URL/noise => "
                "output nothing.\n"
                f"User message: {question}\n"
                "Do not answer the question, only create a relevant title. "
                "Do NOT add quotes around the title.\n"
                "Examples (user question -> title):\n"
                "give me pizza recipe -> Pizza Recipe\n"
                "google founding team members -> Google Founding Team\n"
                "what's the capital of japan -> Japan Capital\n"
                "female of the pig -> Pig Female Name\n"
            )
            return [{"role": "user", "content": prompt}]
        else:
            system_prompt = (
                "You are a very-short-title generator. Return ONLY a concise "
                "title. No punctuation (except apostrophes in possessives), "
                "no quotes, no hashtags, no emojis, no trailing filler words. "
                "Capitalize important words. The title shouldn't be a question.\n"
                "Do not answer the question, only create a relevant title.\n"
                "If the message is empty or meaningless, return nothing.\n"
                "Examples (user question -> title):\n"
                "give me pizza recipe -> Pizza Recipe\n"
                "google founding team members -> Google Founding Team\n"
                "what's the capital of japan -> Japan Capital\n"
                "female of the pig -> Pig Female Name\n"
                "Format: just the title, nothing else."
            )
            user_prompt = f"Create a 2-to-4-word title for:\n{question}"
            merged = f"{system_prompt}\n\n{user_prompt}"
            return [{"role": "user", "content": merged}]

    def _build_query_prompt(
        self,
        question: str,
        history: List[Tuple[str, str]],
        context: dict,
        starred_messages: List[str],
        llm,
        strategy: dict,
        custom_prompt: Optional[str] = None
    ) -> List[dict]:
        """Build the final prompt for query response."""
        # Build system prompt
        size_category = strategy.get("system_prompt_size_category", "medium")
        sys_prompt = build_system_prompt(
            model_name=llm.name,
            size_category=size_category,
            long_term_memory=context.get("long_term_memory"),
            starred_messages=starred_messages if starred_messages else None
        )
        
        # Build context components
        mtm_prompt = ""
        kb_prompt = ""
        custom_prompt_text = ""
        
        if context.get("middle_term_memory"):
            mtm_prompt = "\nThese previous messages could be useful:\n" + "\n".join(
                context["middle_term_memory"]
            )
        
        if context.get("kb_context"):
            kb_prompt = "\nRelevant context from Knowledge Base:\n" + "\n".join(
                context["kb_context"]
            )
        
        if strategy.get("use_custom_prompt") and custom_prompt:
            custom_prompt_text = f"\nAdditional instructions: {custom_prompt}"
        
        # Build conversation history
        final_prompt = []
        max_turns = strategy["max_history_turns"]
        max_messages = max_turns * 2
        
        if len(history) > 0:
            start_idx = max(0, len(history) - max_messages)
            if start_idx % 2 != 0:
                start_idx += 1
            
            for i in range(start_idx, len(history), 2):
                if i < len(history):
                    final_prompt.append({"role": "user", "content": history[i][1]})
                if i + 1 < len(history):
                    final_prompt.append({"role": "assistant", "content": history[i + 1][1]})
        
        # Build current question with context
        question_with_context = ""
        if mtm_prompt:
            question_with_context += mtm_prompt + "\n\n"
        if kb_prompt:
            question_with_context += kb_prompt + "\n\n"
        if custom_prompt_text:
            question_with_context += custom_prompt_text + "\n\n"
        question_with_context += question
        
        # Add system prompt
        if len(final_prompt) == 0:
            # No history: merge system prompt into first user message
            if sys_prompt:
                question_with_context = f"{sys_prompt}\n\n{question_with_context}"
        else:
            # Has history: prepend system prompt to first message
            if sys_prompt:
                final_prompt[0]["content"] = f"{sys_prompt}\n\n{final_prompt[0]['content']}"
        
        final_prompt.append({"role": "user", "content": question_with_context})
        
        return final_prompt
