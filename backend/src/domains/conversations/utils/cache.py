"""
Cache utilities for conversation management.
"""
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Set
import numpy as np
import faiss
from dataclasses import dataclass

from src.core.logging import logger
from src.engines.embedder_engine import Embedder_Engine
from .cache_types import ConversationEmbeddingCache, MessageEmbedding


class ConversationCache:
    """
    Manages caching of conversation summaries and embeddings.
    Implemented as a singleton to ensure one cache instance across the application.
    """
    _instance = None
    _summary_cache: Dict[int, Dict] = {}
    _embedding_cache: Dict[int, ConversationEmbeddingCache] = {}
    _faiss_indexes: Dict[int, faiss.Index] = {}

    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating new ConversationCache singleton instance")
            cls._instance = super(ConversationCache, cls).__new__(cls)
            # Initialize metrics
            cls._instance._cache_hits = 0
            cls._instance._cache_misses = 0
            cls._instance._total_cached_embeddings = 0
        return cls._instance

    def _update_metrics(self, hit: bool = True):
        """Update cache hit/miss metrics."""
        if hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1
        
        if self._cache_hits + self._cache_misses % 100 == 0:
            hit_rate = self._cache_hits / (self._cache_hits + self._cache_misses)
            logger.info(
                f"Cache metrics - Hits: {self._cache_hits}, "
                f"Misses: {self._cache_misses}, "
                f"Hit rate: {hit_rate:.2%}, "
                f"Total cached embeddings: {self._total_cached_embeddings}"
            )

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
        if conversation_id not in self._summary_cache:
            return None, True

        cache_entry = self._summary_cache[conversation_id]
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
        
    def initialize_embedding_cache(
        self,
        conversation_id: int,
        embedding_dim: int
    ) -> None:
        """
        Initialize embedding cache and FAISS index for a conversation.
        
        Args:
            conversation_id: ID of the conversation
            embedding_dim: Dimension of the embeddings
        """
        if conversation_id not in self._embedding_cache:
            self._embedding_cache[conversation_id] = ConversationEmbeddingCache(
                conversation_id=conversation_id,
                messages={},
                last_updated=datetime.now(),
                embedding_dim=embedding_dim,
                total_messages=0
            )
            
            # Initialize FAISS index
            index = faiss.IndexFlatL2(embedding_dim)
            self._faiss_indexes[conversation_id] = index
            logger.info(
                f"Initialized embedding cache for conversation {conversation_id}"
            )

    def add_message_embedding(
        self,
        conversation_id: int,
        message_id: int,
        sender: str,
        content: str,
        embedding: np.ndarray,
        timestamp: datetime
    ) -> None:
        """
        Add a new message embedding to the cache.
        
        Args:
            conversation_id: ID of the conversation
            message_id: ID of the message
            sender: Message sender
            content: Message content
            embedding: Message embedding vector
            timestamp: Message timestamp
        """
        if conversation_id not in self._embedding_cache:
            self.initialize_embedding_cache(
                conversation_id,
                embedding.shape[0]
            )

        cache = self._embedding_cache[conversation_id]
        index = self._faiss_indexes[conversation_id]

        # Add to embedding cache
        cache.add_message(
            message_id=message_id,
            sender=sender,
            content=content,
            embedding=embedding,
            timestamp=timestamp
        )

        # Add to FAISS index
        index.add(embedding.reshape(1, -1))
        logger.info(
            f"Added embedding for message {message_id} "
            f"in conversation {conversation_id}"
        )

    def find_relevant_messages(
        self,
        conversation_id: int,
        query_embedding: np.ndarray,
        k: int
    ) -> List[MessageEmbedding]:
        """
        Find messages similar to the query using FAISS index.
        
        Args:
            conversation_id: ID of the conversation
            query_embedding: Query embedding vector
            k: Number of results to return
            
        Returns:
            List of relevant messages with their embeddings
        """
        if conversation_id not in self._faiss_indexes:
            return []

        cache = self._embedding_cache[conversation_id]
        index = self._faiss_indexes[conversation_id]

        # Adjust k to not exceed number of messages
        k = min(k, cache.total_messages)
        if k == 0:
            return []

        # Search in FAISS index
        _, indices = index.search(
            query_embedding.reshape(1, -1),
            k
        )

        # Get corresponding messages
        results = []
        used_contents = set()

        for idx in indices[0]:
            message = cache.get_message_by_index(int(idx))
            if not message or message.content in used_contents:
                continue

            used_contents.add(message.content)
            results.append(message)

        return results

    def get_cached_messages(
        self, conversation_id: int
    ) -> Optional[ConversationEmbeddingCache]:
        """Get cached messages for a conversation."""
        return self._embedding_cache.get(conversation_id)

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
        self._summary_cache[conversation_id] = {
            "summary": summary,
            "message_count": message_count,
            "generated_at": datetime.now()
        }
        logger.info(
            f"Cached summary for conversation {conversation_id} "
            f"with {message_count} messages"
        )

    def remove_conversation_cache(self, conversation_id: int) -> None:
        """
        Remove all cached data for a conversation.
        
        Args:
            conversation_id: ID of the conversation to remove from cache
        """
        # Remove summary
        if conversation_id in self._summary_cache:
            del self._summary_cache[conversation_id]
            logger.info(f"Removed summary cache for conversation {conversation_id}")

        # Remove embedding cache and FAISS index
        if conversation_id in self._embedding_cache:
            del self._embedding_cache[conversation_id]
            logger.info(f"Removed embedding cache for conversation {conversation_id}")

        if conversation_id in self._faiss_indexes:
            del self._faiss_indexes[conversation_id]
            logger.info(f"Removed FAISS index for conversation {conversation_id}")

    def bulk_remove_conversations(self, conversation_ids: List[int]) -> None:
        """
        Remove all cached data for multiple conversations.
        
        Args:
            conversation_ids: List of conversation IDs to remove
        """
        for conv_id in conversation_ids:
            self.remove_conversation_cache(conv_id)

    def get_cache_stats(self) -> Dict:
        """
        Get statistics about the current cache state.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "summaries": {
                "total_entries": len(self._summary_cache),
                "conversations": [
                    {
                        "id": conv_id,
                        "message_count": data["message_count"],
                        "generated_at": data["generated_at"]
                    }
                    for conv_id, data in self._summary_cache.items()
                ]
            },
            "embeddings": {
                "total_entries": len(self._embedding_cache),
                "conversations": [
                    {
                        "id": cache.conversation_id,
                        "message_count": cache.total_messages,
                        "last_updated": cache.last_updated
                    }
                    for cache in self._embedding_cache.values()
                ]
            }
        }
        return stats

    def clear(self) -> None:
        """Clear all cached data."""
        self._summary_cache.clear()
        self._embedding_cache.clear()
        self._faiss_indexes.clear()
        logger.info("Cleared all cache data")