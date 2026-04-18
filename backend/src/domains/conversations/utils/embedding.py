"""
Embedding and semantic search utilities for conversations.
Handles the generation, caching, and searching of message embeddings.
"""
from datetime import datetime
from typing import List, Tuple
import numpy as np
from contextlib import contextmanager

from src.core.logging import logger
from src.engines.embedder_engine import Embedder_Engine
from src.core.exceptions import EmbeddingError


class ConversationEmbedder:
    """Handles embedding generation and semantic search for conversation messages."""
    
    def __init__(self, embedding_dimension: int = 384):
        """
        Initialize the embedder.
        
        Args:
            embedding_dimension: Dimension of the embeddings to generate
        """
        self._embedder = None
        self._embedding_dimension = embedding_dimension
        logger.info(
            f"Initializing ConversationEmbedder with {embedding_dimension}d embeddings"
        )

    @contextmanager
    def _embedder_context(self):
        """Context manager for embedder lifecycle."""
        try:
            if self._embedder is None:
                logger.debug("Initializing embedder instance")
                self._embedder = Embedder_Engine.get_embedder()
            yield self._embedder
        except Exception as e:
            logger.error(f"Error in embedder context: {str(e)}")
            raise EmbeddingError(f"Embedder error: {str(e)}")
        finally:
            if self._embedder is not None:
                logger.debug("Cleaning up embedder instance")
                Embedder_Engine.cleanup()
                self._embedder = None

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embeddings for a query string.
        
        Args:
            query: The text to embed
            
        Returns:
            Numpy array containing the embedding
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        logger.debug(f"Generating embedding for query: {query[:50]}...")
        
        with self._embedder_context() as embedder:
            try:
                query_emb = embedder.encode(query, convert_to_tensor=True)
                embedding = query_emb.cpu().numpy()
                
                if embedding.shape[0] != self._embedding_dimension:
                    raise EmbeddingError(
                        f"Invalid embedding dimension: {embedding.shape[0]}, "
                        f"expected {self._embedding_dimension}"
                    )
                    
                return embedding
                
            except Exception as e:
                raise EmbeddingError(f"Query embedding failed: {str(e)}")

    def embed_messages(
        self,
        messages: List[str],
        batch_size: int = 32
    ) -> np.ndarray:
        """
        Generate embeddings for a list of messages.
        
        Args:
            messages: List of message texts to embed
            
        Returns:
            Numpy array containing the embeddings
        """
        with self._embedder_context() as embedder:
            msg_embs = embedder.encode(messages, convert_to_tensor=False)
            return np.array(msg_embs)

    def find_relevant_messages(
        self,
        conversation_id: int,
        query: str,
        history: List[Tuple[int, str, str, datetime]],
        n_results: int,
        cache
    ) -> List[Tuple[str, str]]:
        """
        Find messages from history that are semantically relevant to the query.
        Uses cached FAISS index when available, otherwise creates new embeddings.
        
        Args:
            conversation_id: ID of the conversation
            query: The query text
            history: List of (message_id, sender, content, timestamp) tuples
            n_results: Number of relevant messages to return
            cache: ConversationCache instance
            
        Returns:
            List of (sender, message) tuples sorted by relevance to query
        """
        if len(history) < 2:
            return []

        try:
            # Generate query embedding
            query_emb = self.embed_query(query)

            # Check cache for existing embeddings
            cached_data = cache.get_cached_messages(conversation_id)
            
            # If no cache exists or cache is outdated, create new embeddings
            if not cached_data or len(cached_data.messages) != len(history):
                logger.info(
                    f"Creating new embeddings for conversation {conversation_id}"
                )
                
                # Generate embeddings for all messages
                messages = [content for _, _, content, _ in history]
                all_embeddings = self.embed_messages(messages)
                
                # Store in cache
                for i, (msg_id, sender, content, timestamp) in enumerate(history):
                    cache.add_message_embedding(
                        conversation_id=conversation_id,
                        message_id=msg_id,
                        sender=sender,
                        content=content,
                        embedding=all_embeddings[i],
                        timestamp=timestamp
                    )

            # Search for relevant messages
            relevant = cache.find_relevant_messages(
                conversation_id=conversation_id,
                query_embedding=query_emb,
                k=n_results
            )

            # Format results maintaining conversation flow
            result_messages = []
            used_messages = set()

            for msg in relevant:
                if msg.content in used_messages:
                    continue
                used_messages.add(msg.content)

                # Find message in history for context
                for i, (_, sender, content, _) in enumerate(history):
                    if content == msg.content:
                        # For user messages, include assistant's response
                        if sender == "user" and i + 1 < len(history):
                            _, next_sender, next_content, _ = history[i + 1]
                            if next_content not in used_messages:
                                result_messages.append((sender, content))
                                used_messages.add(next_content)
                                result_messages.append((next_sender, next_content))
                        
                        # For assistant messages, include user's question
                        elif sender != "user" and i > 0:
                            _, prev_sender, prev_content, _ = history[i - 1]
                            if prev_content not in used_messages:
                                result_messages.append((prev_sender, prev_content))
                                used_messages.add(content)
                                result_messages.append((sender, content))
                        break

            return result_messages

        except Exception as e:
            logger.exception(f"Error finding relevant messages: {str(e)}")
            return []