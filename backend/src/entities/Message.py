"""SQLAlchemy entity for individual messages within conversations.

Represents a single user or assistant message with metadata for starring, caching,
and timestamp tracking. Messages belong to a Conversation and are ordered by timestamp.

Relationships:
    - conversation: Many-to-one with Conversation (parent session).

Example:
    from src.entities.Message import Message

    msg = Message(
        conversation_id=42,
        sender="user",
        content="What is quantum computing?",
        starred=False
    )
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, event
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from src.database.core import Base
from src.core.logging import logger


class Message(Base):
    """SQLAlchemy model for conversation messages with starring and caching support.

    Stores individual messages within conversations, tracking sender, content, timestamp,
    starred status (for memory injection), and embedding cache status (for RAG optimization).

    Attributes:
        id: Primary key (auto-increment).
        conversation_id: Foreign key to Conversation (parent session).
        sender: Message sender - "user" or "llm" (validated).
        content: Message text content (1-32768 chars, validated).
        timestamp: Message creation timestamp (UTC).
        starred: True if user starred for importance (used in memory injection).
        is_embedding_cached: True if embedding computed and cached (RAG optimization).
        conversation: Relationship to Conversation entity.
        age: Hybrid property returning message age in seconds.

    Example:
        >>> msg = Message(conversation_id=42, sender="user", content="Hello!")
        >>> msg.star()
        >>> print(msg.starred)  # True
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender = Column(String(50), nullable=False)  # "user" or "llm"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    starred = Column(Boolean, default=False, nullable=False)
    is_embedding_cached = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    @validates('sender')
    def validate_sender(self, key: str, sender: str) -> str:
        """Validate sender is either 'user' or 'llm'.

        Args:
            key: Column name ("sender").
            sender: Sender value to validate.

        Returns:
            Validated sender value.

        Raises:
            ValueError: If sender not in ['user', 'llm'].
        """
        if sender not in ['user', 'llm']:
            raise ValueError("Sender must be either 'user' or 'llm'")
        return sender

    @validates('content')
    def validate_content(self, key: str, content: str) -> str:
        """Validate content is non-empty and within size limit.

        Args:
            key: Column name ("content").
            content: Content value to validate.

        Returns:
            Validated content value.

        Raises:
            ValueError: If content empty or exceeds 32K chars.
        """
        if not content or len(content.strip()) == 0:
            raise ValueError("Message content cannot be empty")
        if len(content) > 32768:  # 32K chars limit
            raise ValueError("Message content too long (max 32K chars)")
        return content

    @hybrid_property
    def age(self) -> float:
        """Get message age in seconds since creation.

        Returns:
            Time elapsed in seconds.
        """
        return (datetime.utcnow() - self.timestamp).total_seconds()

    def star(self) -> None:
        """Mark message as starred (important) for memory injection."""
        if not self.starred:
            self.starred = True
            logger.info(f"Message {self.id} starred")

    def unstar(self) -> None:
        """Remove starred status from message."""
        if self.starred:
            self.starred = False
            logger.info(f"Message {self.id} unstarred")

    def __repr__(self) -> str:
        """String representation of the message."""
        return (
            f"<Message(id={self.id}, sender='{self.sender}', "
            f"content='{self.content[:50]}...', starred={self.starred})>"
        )