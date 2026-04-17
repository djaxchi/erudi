"""
Data structures for conversation caching.
Provides strongly-typed classes for managing cached embeddings and metadata.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
import numpy as np
from src.core.logging import logger


@dataclass
class MessageEmbedding:
    """
    Represents a message with its embedding and metadata.
    Tracks message content, embedding, and indexing information.
    """
    message_id: int
    sender: str
    content: str
    embedding: np.ndarray
    index_position: int
    timestamp: datetime
    embedding_dimension: int = field(init=False)
    cached_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate embedding after initialization."""
        self.embedding_dimension = self.embedding.shape[0]
        if not isinstance(self.embedding, np.ndarray):
            raise ValueError("Embedding must be a numpy array")
        if len(self.embedding.shape) != 1:
            raise ValueError("Embedding must be a 1D array")
        if self.sender not in ["user", "llm"]:
            raise ValueError("Sender must be 'user' or 'llm'")
        logger.debug(
            f"Created MessageEmbedding for message {self.message_id} "
            f"with {self.embedding_dimension}d embedding"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.
        Embedding is handled separately to avoid numpy serialization issues.
        """
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "content": self.content,
            "index_position": self.index_position,
            "timestamp": self.timestamp.isoformat(),
            "embedding_dimension": self.embedding_dimension,
            "cached_at": self.cached_at.isoformat()
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        embedding: np.ndarray
    ) -> "MessageEmbedding":
        """
        Create instance from dictionary and embedding array.
        
        Args:
            data: Dictionary containing message metadata
            embedding: Numpy array containing the message embedding
            
        Returns:
            New MessageEmbedding instance
            
        Raises:
            ValueError: If data is invalid
        """
        if embedding.shape[0] != data.get("embedding_dimension"):
            raise ValueError(
                f"Embedding dimension mismatch: {embedding.shape[0]} vs "
                f"{data.get('embedding_dimension')}"
            )
        
        return cls(
            message_id=data["message_id"],
            sender=data["sender"],
            content=data["content"],
            embedding=embedding,
            index_position=data["index_position"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class ConversationEmbeddingCache:
    """
    Cache for conversation message embeddings.
    Manages message embeddings and provides FAISS-compatible matrix operations.
    """
    conversation_id: int
    messages: Dict[int, MessageEmbedding] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    embedding_dim: int = 384  # Default dimension
    total_messages: int = 0
    deleted_messages: Set[int] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "conversation_id": self.conversation_id,
            "messages": {
                str(k): v.to_dict()
                for k, v in self.messages.items()
            },
            "last_updated": self.last_updated.isoformat(),
            "embedding_dim": self.embedding_dim,
            "total_messages": self.total_messages,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        embeddings: Dict[int, np.ndarray]
    ) -> "ConversationEmbeddingCache":
        """Create instance from dictionary and embeddings map."""
        return cls(
            conversation_id=data["conversation_id"],
            messages={
                int(k): MessageEmbedding.from_dict(v, embeddings[int(k)])
                for k, v in data["messages"].items()
            },
            last_updated=datetime.fromisoformat(data["last_updated"]),
            embedding_dim=data["embedding_dim"],
            total_messages=data["total_messages"],
        )

    def get_embeddings_matrix(self) -> np.ndarray:
        """
        Get all embeddings as a matrix in index order.
        
        Returns:
            Matrix of shape (n_messages, embedding_dim)
        """
        # Sort by index position to maintain correct order
        sorted_messages = sorted(
            self.messages.values(),
            key=lambda x: x.index_position
        )
        return np.vstack([msg.embedding for msg in sorted_messages])

    def get_message_by_index(self, index: int) -> Optional[MessageEmbedding]:
        """Get message by its index position."""
        for msg in self.messages.values():
            if msg.index_position == index:
                return msg
        return None

    def add_message(
        self,
        message_id: int,
        sender: str,
        content: str,
        embedding: np.ndarray,
        timestamp: datetime
    ) -> None:
        """Add a new message to the cache."""
        self.messages[message_id] = MessageEmbedding(
            message_id=message_id,
            sender=sender,
            content=content,
            embedding=embedding,
            index_position=self.total_messages,
            timestamp=timestamp
        )
        self.total_messages += 1
        self.last_updated = datetime.now()

    def remove_message(self, message_id: int) -> None:
        """Remove a message and update index positions."""
        if message_id not in self.messages:
            return

        removed_pos = self.messages[message_id].index_position
        del self.messages[message_id]

        # Update positions for all messages after the removed one
        for msg in self.messages.values():
            if msg.index_position > removed_pos:
                msg.index_position -= 1

        self.total_messages -= 1
        self.last_updated = datetime.now()