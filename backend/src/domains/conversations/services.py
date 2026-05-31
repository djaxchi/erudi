"""Services for conversation management and streaming AI generation.

Business logic for the conversation lifecycle and streaming generation. Since the
LangChain refactor, generation goes through ``AgentRunner`` (one ``create_agent``
per turn, history persisted in the LangGraph checkpointer) instead of the
hand-rolled prompt/engine loop. The SQLAlchemy ``Message``/``Conversation`` tables
remain the source of truth for display (fetch_messages, starred, timestamps); the
checkpointer holds the agent's working state and rolling summary.

Layering: streaming methods are async generators (the FastAPI ``StreamingResponse``
consumes them directly on the event loop); all synchronous SQLAlchemy work is
wrapped in ``run_in_threadpool`` so DB commits never block the loop.
"""

from typing import AsyncGenerator, List, Optional

from fastapi.concurrency import run_in_threadpool

from src.core.logging import logger
from src.core import config
from src.agents.prompts import build_agent_system_prompt
from src.agents.runner import AgentRunner, GenParams, ERROR_MESSAGE
from src.domains.conversations.repository import ConversationRepository, MessageRepository
from src.domains.conversations.schemas import ConversationQuery
from src.entities.Conversation import Conversation
from src.entities.Llm import Llm
from src.core.exceptions import ModelNotFoundException


class ConversationService:
    """Service for managing conversations and message processing."""

    def __init__(self, db, checkpointer=None):
        """Initialize the service.

        Args:
            db: SQLAlchemy session for repository operations.
            checkpointer: LangGraph checkpointer (app-wide ``AsyncSqliteSaver``)
                for stateful conversations. ``None`` runs the agent statelessly
                (used by tests that don't exercise persistence).
        """
        logger.debug("Initializing ConversationService")
        self.conversation_repo = ConversationRepository(db)
        self.message_repo = MessageRepository(db)
        self.checkpointer = checkpointer
        self.runner = AgentRunner(checkpointer)
        self.db = db

    # ===================== Synchronous CRUD =====================
    def create_conversation(
        self,
        llm_id: int,
        temperature: float = 0.2,
        top_p: float = 0.5,
        max_tokens: int = 1024,
        custom_prompt: str = "",
    ) -> Conversation:
        """Create a new conversation with the given LLM and generation params."""
        logger.info(f"Creating new conversation with LLM {llm_id}")
        return self.conversation_repo.create_conversation(
            llm_id=llm_id,
            name="New Conversation",
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            custom_prompt=custom_prompt,
        )

    def update_conversation(
        self,
        conversation_id: int,
        name: Optional[str] = None,
        llm_id: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        custom_prompt: Optional[str] = None,
    ) -> Conversation:
        """Partial update of conversation metadata (only non-None fields)."""
        logger.info(f"Updating conversation {conversation_id}")
        return self.conversation_repo.update_conversation(
            conversation_id=conversation_id,
            name=name,
            llm_id=llm_id,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            custom_prompt=custom_prompt,
        )

    # ===================== Deletion (DB + checkpointer thread) =====================
    async def delete_conversation(self, conversation_id: int) -> None:
        """Delete a conversation and purge its checkpointer thread.

        Both stores must be cleared: SQLite autoincrement reuses ids, so a stale
        checkpointer thread would otherwise leak a deleted conversation's agent
        context into a future conversation with the same id (review BLOCKER B3).
        """
        logger.info(f"Deleting conversation {conversation_id}")
        await run_in_threadpool(self._delete_conversation_db, conversation_id)
        await self._purge_thread(conversation_id)

    async def delete_conversations_bulk(self, conversation_ids: List[int]) -> None:
        """Bulk-delete conversations and purge each checkpointer thread (B3)."""
        logger.info(f"Bulk deleting {len(conversation_ids)} conversations")
        await run_in_threadpool(self._delete_conversations_bulk_db, conversation_ids)
        for conversation_id in conversation_ids:
            await self._purge_thread(conversation_id)

    def _delete_conversation_db(self, conversation_id: int) -> None:
        self.conversation_repo.delete_conversation(conversation_id)
        self.db.commit()

    def _delete_conversations_bulk_db(self, conversation_ids: List[int]) -> None:
        self.conversation_repo.delete_conversations_bulk(conversation_ids)
        self.db.commit()

    async def _purge_thread(self, conversation_id: int) -> None:
        if self.checkpointer is None:
            return
        try:
            await self.checkpointer.adelete_thread(str(conversation_id))
        except Exception:
            logger.exception(
                f"Failed to purge checkpointer thread for conversation {conversation_id}"
            )

    def store_error_message(self, conversation_id: int) -> int:
        """Persist a fallback error message (called by the frontend on failure)."""
        logger.info(f"Storing error message for conversation {conversation_id}")
        message = self.message_repo.create_message(
            conversation_id=conversation_id,
            content=ERROR_MESSAGE,
            sender="llm",
        )
        self.conversation_repo.update_last_message_time(conversation_id)
        config.LLM_Engine.cleanup()
        return message.id

    # ===================== Streaming generation =====================
    async def query_and_respond_stream(
        self,
        conversation_id: int,
        payload: ConversationQuery,
    ) -> AsyncGenerator[str, None]:
        """Stream the agent's response token-by-token (raw text/plain).

        Persists the user message up front (so it shows immediately) and the
        assistant message after streaming. The agent restores prior history from
        the checkpointer, so only the new message is sent.
        """
        logger.info(f"Processing query for conversation {conversation_id}")

        try:
            conversation, llm = await run_in_threadpool(
                self._load_conversation_and_llm, conversation_id
            )
        except Exception:
            logger.exception("Failed to load conversation/LLM for query")
            yield ERROR_MESSAGE
            return

        assistant_response = ""
        try:
            await run_in_threadpool(self._persist_user_message, conversation_id, payload.question)

            starred = await run_in_threadpool(
                self.message_repo.get_starred_messages, conversation_id
            )
            system_prompt = build_agent_system_prompt(
                llm, starred_messages=starred, custom_prompt=payload.custom_prompt
            )
            params = GenParams(
                temperature=payload.temperature if payload.temperature is not None else conversation.temperature,
                top_p=payload.top_p if payload.top_p is not None else conversation.top_p,
                max_tokens=payload.max_new_tokens or conversation.max_tokens or 1024,
            )

            async for token in self.runner.astream_text(
                llm=llm,
                user_message=payload.question,
                system_prompt=system_prompt,
                params=params,
                thread_id=str(conversation_id),
                summarize=True,
            ):
                assistant_response += token
                yield token
        except Exception:
            logger.exception("Query streaming failed")
            if not assistant_response:
                assistant_response = ERROR_MESSAGE
                yield ERROR_MESSAGE
        finally:
            await run_in_threadpool(
                self._persist_assistant_message, conversation_id, assistant_response
            )

    async def generate_title_stream(
        self,
        conversation_id: int,
        question: str,
    ) -> AsyncGenerator[str, None]:
        """Stream an auto-generated 2–4 word title (stateless one-shot)."""
        logger.info(f"Generating title for conversation {conversation_id}")

        try:
            _conversation, llm = await run_in_threadpool(
                self._load_conversation_and_llm, conversation_id
            )
        except Exception:
            logger.exception("Title gen: failed to load conversation/LLM")
            await run_in_threadpool(self._save_title, conversation_id, "New Conversation")
            return

        if not question or not question.strip():
            await run_in_threadpool(self._save_title, conversation_id, "New Conversation")
            return

        prompt_text = self._build_title_prompt_text(question, llm.type)
        temperature = 0.5 if llm.type == "mistral" else 1.0
        top_p = 0.9 if llm.type == "mistral" else 0.95

        generated_title = ""
        try:
            async for chunk in self.runner.astream_oneshot(
                llm=llm,
                prompt_text=prompt_text,
                temperature=temperature,
                top_p=top_p,
                max_tokens=12,
            ):
                generated_title += chunk
                yield chunk
        finally:
            final_title = generated_title.strip() or "New Conversation"
            await run_in_threadpool(self._save_title, conversation_id, final_title)

    # ===================== Sync DB helpers (run in threadpool) =====================
    def _load_conversation_and_llm(self, conversation_id: int):
        """Load the conversation + its LLM, auto-repairing a stale ``llm_id``."""
        conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
        try:
            llm = self.conversation_repo.get_llm_by_id(conversation.llm_id)
        except ModelNotFoundException:
            logger.warning(
                f"LLM id={conversation.llm_id} not found for conversation "
                f"{conversation_id}, attempting auto-repair"
            )
            local_llm = self.db.query(Llm).filter(Llm.local == 1).first()
            if local_llm is None:
                raise ModelNotFoundException(
                    f"LLM {conversation.llm_id} not found and no local models available"
                )
            logger.info(
                f"Auto-repairing conversation {conversation_id}: "
                f"llm_id {conversation.llm_id} -> {local_llm.id} ({local_llm.name})"
            )
            conversation.llm_id = local_llm.id
            self.db.commit()
            llm = local_llm
        return conversation, llm

    def _persist_user_message(self, conversation_id: int, content: str) -> None:
        self.message_repo.create_message(
            conversation_id=conversation_id, sender="user", content=content
        )
        self.conversation_repo.update_last_message_time(conversation_id)
        self.db.commit()

    def _persist_assistant_message(self, conversation_id: int, content: str) -> None:
        self.message_repo.create_message(
            conversation_id=conversation_id, sender="llm", content=content.strip()
        )
        self.conversation_repo.update_last_message_time(conversation_id)
        self.db.commit()

    def _save_title(self, conversation_id: int, title: str) -> None:
        conversation = self.conversation_repo.get_conversation_by_id(conversation_id)
        conversation.name = title
        self.db.commit()

    def _build_title_prompt_text(self, question: str, model_type: str) -> str:
        """Single merged user-message prompt for title generation (2–4 words)."""
        if model_type == "mistral":
            return (
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
        return f"{system_prompt}\n\n{user_prompt}"
