"""
Entity representing a conversation in the application.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Text, event
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from src.database.core import Base
from src.core.logging import logger


class Conversation(Base):
    """SQLAlchemy model for conversations."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    llm_id = Column(Integer, ForeignKey("llms.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Conversation parameters
    temperature = Column(Float, default=1.0)
    top_p = Column(Float, default=0.95)
    max_tokens = Column(Integer, default=1024)
    custom_prompt = Column(Text, default="")
    name = Column(String(255), nullable=False, index=True, default="New Conversation")

    # Relationships
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.timestamp"
    )
    llm = relationship("Llm", back_populates="conversations")

    @validates('temperature')
    def validate_temperature(self, key: str, temperature: float) -> float:
        """Validate temperature parameter."""
        if not 0.0 <= temperature <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return temperature

    @validates('top_p')
    def validate_top_p(self, key: str, top_p: float) -> float:
        """Validate top_p parameter."""
        if not 0.0 <= top_p <= 1.0:
            raise ValueError("Top_p must be between 0.0 and 1.0")
        return top_p

    @validates('max_tokens')
    def validate_max_tokens(self, key: str, max_tokens: int) -> int:
        """Validate max_tokens parameter."""
        if not 1 <= max_tokens <= 32768:
            raise ValueError("Max tokens must be between 1 and 32768")
        return max_tokens

    @hybrid_property
    def message_count(self) -> int:
        """Get the number of messages in the conversation."""
        return len(self.messages)

    @hybrid_property
    def last_message_time(self) -> Optional[datetime]:
        """Get the timestamp of the last message."""
        if self.messages:
            return max(msg.timestamp for msg in self.messages)
        return self.created_at

    def add_message(self, content: str, sender: str) -> "Message":
        """
        Add a new message to the conversation.
        
        Args:
            content: Message content
            sender: Message sender ("user" or "llm")
            
        Returns:
            The created Message instance
        """
        from src.entities.Message import Message
        message = Message(
            conversation_id=self.id,
            content=content,
            sender=sender
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        return message

    def __repr__(self) -> str:
        """String representation of the conversation."""
        return (
            f"<Conversation(id={self.id}, name='{self.name}', "
            f"messages={self.message_count})>"
        )