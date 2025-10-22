"""
Entity representing a message in a conversation.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, event
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from src.database.core import Base
from src.core.logging import logger


class Message(Base):
    """SQLAlchemy model for conversation messages."""
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
        """Validate message sender."""
        if sender not in ['user', 'llm']:
            raise ValueError("Sender must be either 'user' or 'llm'")
        return sender

    @validates('content')
    def validate_content(self, key: str, content: str) -> str:
        """Validate message content."""
        if not content or len(content.strip()) == 0:
            raise ValueError("Message content cannot be empty")
        if len(content) > 32768:  # 32K chars limit
            raise ValueError("Message content too long (max 32K chars)")
        return content

    @hybrid_property
    def age(self) -> float:
        """Get message age in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()

    def star(self) -> None:
        """Star this message."""
        if not self.starred:
            self.starred = True
            logger.info(f"Message {self.id} starred")

    def unstar(self) -> None:
        """Unstar this message."""
        if self.starred:
            self.starred = False
            logger.info(f"Message {self.id} unstarred")

    def __repr__(self) -> str:
        """String representation of the message."""
        return (
            f"<Message(id={self.id}, sender='{self.sender}', "
            f"content='{self.content[:50]}...', starred={self.starred})>"
        )