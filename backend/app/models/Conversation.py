from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Text
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    llm_id = Column(Integer, ForeignKey("llms.id"), nullable=False)  # ID of the LLM
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Conversation-specific parameters
    temperature = Column(Float, default=0.2)
    top_p = Column(Float, default=0.5) 
    max_tokens = Column(Integer, default=1024)
    custom_prompt = Column(Text, default="")

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    last_message_time = Column(DateTime, default=datetime.utcnow)
    name = Column(String, nullable=False, index=True, default="New Conversation")