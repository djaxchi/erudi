"""
Context management utilities for conversations.
"""
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.entities.Llm import Llm
from src.utils.kb_utils import get_relevant_texts_from_kb
from .cache import ConversationCache
from .embedding import ConversationEmbedder
from .prompt import PromptBuilder


class ConversationContext:
    """
    Manages conversation context, including history processing, relevance
    search, and context assembly.
    """
    def __init__(self):
        self.cache = ConversationCache()
        self.embedder = ConversationEmbedder()
        self.prompt_builder = PromptBuilder()

    def _should_use_long_term_memory(
        self, strategy: Dict, history: List, n_last_turns: int
    ) -> bool:
        """Check if long-term memory should be used."""
        summary_threshold = n_last_turns * 2 * 2
        return (
            strategy.get("use_long_term_memory", False)
            and len(history) > summary_threshold
        )

    def _should_use_middle_term_memory(
        self, strategy: Dict, history: List
    ) -> bool:
        """Check if middle-term memory should be used."""
        return (
            strategy.get("use_middle_term_memory", False)
            and len(history) >= 2
        )

    def _get_or_generate_summary(
        self,
        conversation_id: int,
        current_message_count: int,
        history: List[Tuple[str, str]],
        model_type: str
    ) -> Optional[str]:
        """Get cached summary or generate new one."""
        summary, need_regenerate = self.cache.get_summary(
            conversation_id,
            current_message_count
        )

        if need_regenerate:
            logger.info(
                f"Generating new conversation summary for {len(history)} messages"
            )
            summary = self._generate_conversation_summary(history, model_type)
            if summary:
                self.cache.store_summary(
                    conversation_id,
                    summary,
                    current_message_count + 1
                )

        return summary

    def _generate_conversation_summary(
        self,
        history: List[Tuple[str, str]],
        model_type: str = "mistral"
    ) -> str:
        """Generate a summary of the conversation history."""
        try:
            # Convert history to formatted text
            formatted_history = []
            for _, sender, message, _ in history:
                formatted_history.append(f"{sender}: {message}")
            
            conversation_text = "\n".join(formatted_history)
            
            # Use different prompts based on model type
            if model_type == "mistral":
                prompt = (
                    "Please provide a concise summary of this conversation, "
                    "highlighting the main topics and key points discussed:\n\n"
                    f"{conversation_text}"
                )
            else:
                prompt = (
                    "Summarize the following conversation:\n\n"
                    f"{conversation_text}"
                )
            
            # TODO: Implement actual summarization using the appropriate model
            # For now, return a placeholder
            return "Conversation summary placeholder"
            
        except Exception as e:
            logger.error(f"Error generating conversation summary: {str(e)}")
            return ""

    def retrieve_context(
        self,
        query: str,
        conversation_history: List[Tuple[str, str]],
        conversation_id: int,
        llm: Llm,
        db: Session,
        strategy: Dict,
        n_last_turns: int = 1,
        model_type: str = "mistral",
    ) -> Dict:
        """
        Retrieve relevant context for the current query.
        
        Args:
            query: The user's query
            conversation_history: List of (sender, message) tuples
            conversation_id: The conversation ID
            llm: The LLM being used
            db: Database session
            strategy: Prompting strategy configuration
            n_last_turns: Number of recent turns to include
            model_type: Type of model being used
            
        Returns:
            Dictionary containing various types of context
        """
        context = {
            "context_str": None,
            "long_term_memory": None,
            "middle_term_memory": None,
            "kb_context": None,
        }

        current_message_count = len(conversation_history)

        # Long-term memory (Conversation summary)
        if self._should_use_long_term_memory(
            strategy,
            conversation_history,
            n_last_turns
        ):
            summary = self._get_or_generate_summary(
                conversation_id,
                current_message_count,
                conversation_history,
                model_type
            )
            if summary:
                context["long_term_memory"] = summary

        # Middle-term memory (Semantic context)
        if self._should_use_middle_term_memory(strategy, conversation_history):
            n_to_retrieve = min(
                strategy.get("mtm_top_k", 4),
                len(conversation_history) // 2
            )
            relevant_messages = self.embedder.find_relevant_messages(
                conversation_id,
                query,
                conversation_history,
                n_to_retrieve,
                self.cache
            )
            if relevant_messages:
                context["middle_term_memory"] = relevant_messages

        # Knowledge Base Context
        if llm.is_attached_to_kb and (
            strategy.get("use_kb_basic", False) or
            strategy.get("use_kb_enhanced", False)
        ):
            try:
                from src.utils.kb_utils import get_relevant_texts_from_kb
                kb_context = get_relevant_texts_from_kb(
                    query=query,
                    llm=llm,
                    db=db,
                    kb_top_k=strategy.get("kb_top_k", 3)
                )
                if kb_context:
                    context["kb_context"] = kb_context
            except Exception:
                logger.exception("Failed to retrieve Knowledge Base context")

        # Build the final context string
        context_elements = []

        if context["long_term_memory"]:
            context_elements.append(
                f"Previous conversation summary:\n{context['long_term_memory']}\n"
            )

        if context["middle_term_memory"]:
            context_elements.append(
                "Relevant previous exchanges:\n" +
                "\n".join([
                    f"{sender}: {message}"
                    for sender, message in context["middle_term_memory"]
                ]) + "\n"
            )

        if context["kb_context"]:
            context_elements.append(
                "Relevant knowledge:\n" +
                "\n".join(context["kb_context"]) + "\n"
            )

        # Add recent messages based on strategy
        if strategy.get("use_short_term_memory", True):
            n_recent = n_last_turns * 2
            recent_messages = (
                conversation_history[-n_recent:]
                if len(conversation_history) >= n_recent
                else conversation_history
            )
            if recent_messages:
                context_elements.append(
                    "Recent messages:\n" +
                    "\n".join([
                        f"{sender}: {message}"
                        for _, sender, message, _ in recent_messages
                    ])
                )

        if context_elements:
            context["context_str"] = "\n\n".join(context_elements)

        return context

    def _should_use_long_term_memory(
        self, strategy: Dict, history: List, n_last_turns: int
    ) -> bool:
        """Check if long-term memory should be used."""
        summary_threshold = n_last_turns * 2 * 2
        return (
            strategy.get("use_long_term_memory", False)
            and len(history) > summary_threshold
        )

    def _should_use_middle_term_memory(
        self, strategy: Dict, history: List
    ) -> bool:
        """Check if middle-term memory should be used."""
        return (
            strategy.get("use_middle_term_memory", False)
            and len(history) >= 2
        )

    def _should_use_kb_context(self, strategy: Dict, llm: Llm) -> bool:
        """Check if knowledge base context should be used."""
        return (
            llm.is_attached_to_kb
            and (
                strategy.get("use_kb_basic", False)
                or strategy.get("use_kb_enhanced", False)
            )
        )

    def _get_or_generate_summary(
        self,
        conversation_id: int,
        current_message_count: int,
        history: List[Tuple[str, str]],
        model_type: str
    ) -> Optional[str]:
        """Get cached summary or generate new one."""
        summary = self.get_cached_summary(conversation_id, current_message_count)
        if not summary:
            summary = self.generate_conversation_summary(history, model_type)
            if summary:
                self.cache_summary(conversation_id, summary, current_message_count)
        return summary

    def _get_relevant_messages(
        self,
        query: str,
        history: List[Tuple[str, str]],
        n_last_turns: int
    ) -> List[Tuple[str, str]]:
        """Get messages relevant to the query using semantic search."""
        try:
            # Prepare messages for embedding
            messages = [msg for _, msg in history]
            
            # Get embeddings and find relevant messages
            relevant_indices = self._embedder.get_relevant_indices(
                query, messages, top_k=n_last_turns*2
            )
            
            return [history[i] for i in relevant_indices]
        except Exception as e:
            logger.error(f"Error getting relevant messages: {str(e)}")
            return []

    def _get_kb_context(
        self, query: str, llm: Llm, db: Session
    ) -> List[str]:
        """Get relevant context from knowledge base."""
        try:
            return get_relevant_texts_from_kb(query, llm, db)
        except Exception as e:
            logger.error(f"Error getting KB context: {str(e)}")
            return []

    def _get_recent_messages(
        self,
        history: List[Tuple[str, str]],
        n_last_turns: int
    ) -> List[Tuple[str, str]]:
        """Get the most recent messages."""
        n_recent = n_last_turns * 2
        return history[-n_recent:] if len(history) >= n_recent else history

    def _format_relevant_messages(
        self, messages: List[Tuple[str, str]]
    ) -> List[str]:
        """Format relevant messages for context."""
        return [
            f"Relevant exchange:\n{sender}: {message}\n"
            for sender, message in messages
        ]

    def _format_kb_context(self, kb_context: List[str]) -> List[str]:
        """Format knowledge base context."""
        return [
            f"Related knowledge:\n{context}\n"
            for context in kb_context
        ]

    def _format_recent_messages(
        self, messages: List[Tuple[str, str]]
    ) -> List[str]:
        """Format recent messages for context."""
        return [
            f"{sender}: {message}"
            for sender, message in messages
        ]