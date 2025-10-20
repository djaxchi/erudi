"""
Embedding and semantic search utilities for conversations.
"""
from typing import List, Tuple
import numpy as np
import faiss
from src.core.logging import logger
from src.utils.inference_utils import EmbedderService


class ConversationEmbedder:
    """
    Handles embedding generation and semantic search for conversation messages.
    """
    def __init__(self):
        self._embedder = None

    def _ensure_embedder(self):
        """Initialize embedder if not already done."""
        if self._embedder is None:
            self._embedder = EmbedderService.get_embedder()

    def _cleanup_embedder(self):
        """Clean up embedder resources."""
        if self._embedder is not None:
            EmbedderService.cleanup()
            self._embedder = None

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embeddings for a query string.
        
        Args:
            query: The text to embed
            
        Returns:
            Numpy array containing the embedding
        """
        try:
            self._ensure_embedder()
            query_emb = self._embedder.encode(query, convert_to_tensor=True)
            return query_emb.cpu().numpy()
        finally:
            self._cleanup_embedder()

    def embed_messages(self, messages: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of messages.
        
        Args:
            messages: List of message texts to embed
            
        Returns:
            Numpy array containing the embeddings
        """
        try:
            self._ensure_embedder()
            msg_embs = self._embedder.encode(messages, convert_to_tensor=False)
            return np.array(msg_embs)
        finally:
            self._cleanup_embedder()

    def find_relevant_messages(
        self,
        query: str,
        history: List[Tuple[str, str]],
        n_results: int
    ) -> List[Tuple[str, str]]:
        """
        Find messages from history that are semantically relevant to the query.
        
        Args:
            query: The query text
            history: List of (sender, message) tuples representing conversation history
            n_results: Number of relevant messages to return
            
        Returns:
            List of (sender, message) tuples sorted by relevance to query
        """
        if len(history) < 2:
            return []

        try:
            # Extract just the message content for embedding
            messages = [msg for _, msg in history]
            
            # Generate embeddings
            query_emb = self.embed_query(query)
            msg_embs = self.embed_messages(messages)

            # Create FAISS index for similarity search
            index = faiss.IndexFlatL2(msg_embs.shape[1])
            index.add(msg_embs)

            # Search for similar messages
            _, indices = index.search(
                query_emb.reshape(1, -1),
                k=min(n_results, len(messages))
            )

            # Return original messages with sender information
            relevant_messages = []
            used_messages = set()

            for idx in indices[0]:
                sender, msg = history[idx]
                
                # Skip if we've already included this message
                if msg in used_messages:
                    continue
                used_messages.add(msg)

                # For user messages, try to include the assistant's response
                if sender == "user" and idx + 1 < len(history):
                    next_sender, next_msg = history[idx + 1]
                    if next_msg not in used_messages:
                        relevant_messages.append((sender, msg))
                        used_messages.add(next_msg)
                        relevant_messages.append((next_sender, next_msg))

                # For assistant messages, try to include the user's question
                elif sender != "user" and idx > 0:
                    prev_sender, prev_msg = history[idx - 1]
                    if prev_msg not in used_messages:
                        relevant_messages.append((prev_sender, prev_msg))
                        used_messages.add(prev_msg)
                        relevant_messages.append((sender, msg))

            return relevant_messages

        except Exception as e:
            logger.exception(f"Error finding relevant messages: {str(e)}")
            return []