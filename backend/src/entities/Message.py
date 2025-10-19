from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from src.database.core import Base
from datetime import datetime

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender = Column(String, nullable=False)  # "user" or "llm"
    content = Column(String, nullable=False)  # The message content
    timestamp = Column(DateTime, default=datetime.utcnow)
    starred = Column(Boolean, default=False, nullable=False)  # True if starred
    conversation = relationship("Conversation", back_populates="messages")