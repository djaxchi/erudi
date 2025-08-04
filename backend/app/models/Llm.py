from app.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

class Llm(Base):
    __tablename__ = "llms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) # defiines if the model is downloaded or not
    local = Column(Integer, nullable=False) # defines local or not
    link = Column(String, nullable=True) #  local link if dowloaded huggingface link othewise
    type = Column(String, nullable=False)  # Type of the model (e.g., "mistral", "gemma")
    description = Column(String, nullable=True)  # Optional description of the model
    is_attached_to_kb = Column(Integer, default=0)  # 0 or 1 Indicates if the model is attached to a knowledge base
    kb_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="SET NULL"), nullable=True)  # Foreign key to the knowledge base if attached

    kb = relationship("KnowledgeBase", back_populates="llm", uselist=False)
        
    __table_args__ = (
        {"sqlite_autoincrement": True}
    )