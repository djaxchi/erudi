"""
Cache utilities for conversation management.
"""
from datetime import datetime
from typing import Dict, Optional, Tuple
from src.core.logging import logger


class ConversationCache:
    """
    Manages caching of conversation summaries and other conversation-related data.
    Implemented as a singleton to ensure one cache instance across the application.
    """
    _instance = None
    _cache: Dict[int, Dict] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConversationCache, cls).__new__(cls)
        return cls._instance

    def get_summary(
        self, conversation_id: int, current_message_count: int
    ) -> Tuple[Optional[str], bool]:
        """
        Get cached summary or determine if regeneration is needed.
        
        Args:
            conversation_id: ID of the conversation
            current_message_count: Current number of messages in conversation
            
        Returns:
            Tuple of (cached_summary, needs_regeneration)
        """
        if conversation_id not in self._cache:
            return None, True

        cache_entry = self._cache[conversation_id]
        cached_count = cache_entry["message_count"]

        if current_message_count >= cached_count * 2:
            logger.info(
                f"Summary cache expired for conversation {conversation_id}: "
                f"{cached_count} -> {current_message_count} messages"
            )
            return None, True

        logger.info(
            f"Using cached summary for conversation {conversation_id}: "
            f"{cached_count} messages"
        )
        return cache_entry["summary"], False

    def store_summary(
        self, conversation_id: int, summary: str, message_count: int
    ) -> None:
        """
        Cache a generated conversation summary.
        
        Args:
            conversation_id: ID of the conversation
            summary: Generated summary text
            message_count: Current message count when summary was generated
        """
        self._cache[conversation_id] = {
            "summary": summary,
            "message_count": message_count,
            "generated_at": datetime.now()
        }
        logger.info(
            f"Cached summary for conversation {conversation_id} "
            f"with {message_count} messages"
        )

    def remove_summary(self, conversation_id: int) -> None:
        """
        Remove a conversation's cached summary.
        
        Args:
            conversation_id: ID of the conversation to remove from cache
        """
        if conversation_id in self._cache:
            del self._cache[conversation_id]
            logger.info(f"Removed summary from cache for conversation {conversation_id}")

    def bulk_remove_summaries(self, conversation_ids: list[int]) -> None:
        """
        Remove cached summaries for multiple conversations.
        
        Args:
            conversation_ids: List of conversation IDs to remove from cache
        """
        for conv_id in conversation_ids:
            self.remove_summary(conv_id)
            logger.info(f"Removed summary from cache for conversation {conv_id}")

    def get_cache_stats(self) -> Dict:
        """
        Get statistics about the current cache state.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "total_entries": len(self._cache),
            "conversations": [
                {
                    "id": conv_id,
                    "message_count": data["message_count"],
                    "generated_at": data["generated_at"]
                }
                for conv_id, data in self._cache.items()
            ]
        }
        return stats

    def clear(self) -> None:
        """Clear all cached summaries."""
        self._cache.clear()
        logger.info("Cleared all summaries from cache")