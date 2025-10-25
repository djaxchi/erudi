"""SQLAlchemy entity for LLM model catalog and metadata.

This entity represents the complete lifecycle of an LLM model in Erudi:
- **Remote models**: Browsable from HuggingFace (local=0).
- **Downloading**: Temporary placeholder during download (local=2).
- **Local models**: Downloaded and ready for inference (local=1).
- **KB-attached**: Specialized assistants with Knowledge Base (is_attached_to_kb=1).

Relationships:
    - kb: One-to-one with KnowledgeBase (if is_attached_to_kb=1).

Example:
    from src.entities.Llm import Llm

    # Create remote model entry
    llm = Llm(
        name="Llama-3-8B-Instruct",
        local=0,
        link="meta-llama/Meta-Llama-3-8B-Instruct",
        type="llama",
        param_size=8.0,
        quantized=0
    )
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Float
from src.database.core import Base
from sqlalchemy.orm import relationship

class Llm(Base):
    """SQLAlchemy model for LLM catalog entries with download state and KB attachment.

    Represents a single LLM model in the database, tracking its download status,
    metadata, and optional Knowledge Base attachment. Models can be remote (browsable),
    downloading (temporary), or local (ready for inference).

    Attributes:
        id: Primary key (auto-increment).
        name: Human-readable model name (e.g., "Llama-3-8B-Instruct").
        local: Download state - 0=remote (HuggingFace), 1=local (ready), 2=downloading.
        link: HuggingFace repo ID (if remote) or local filesystem path (if local).
        type: Model family (e.g., "llama", "qwen", "mistral", "gemma").
        description: Optional user annotation or HuggingFace description.
        model_metadata: JSON string with additional metadata (vocab size, context length).
        quantized: 0=not quantized (full precision), 1=pre-quantized (MLX/GGUF format).
        param_size: Model size in billions of parameters (2, 4, 8, 16, 70, etc.).
        is_attached_to_kb: 0=standalone model, 1=specialized KB assistant.
        kb_id: Foreign key to KnowledgeBase (if is_attached_to_kb=1).
        kb: Relationship to KnowledgeBase entity (one-to-one).

    Example:
        >>> llm = Llm(name="Qwen2.5-7B", local=1, link="/data/models/42", type="qwen", param_size=7.0)
        >>> db.add(llm)
        >>> db.commit()
    """
    __tablename__ = "llms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) # defiines if the model is downloaded or not
    local = Column(Integer, nullable=False) # defines local path if model is local, huggingface link othewise
    link = Column(String, nullable=True)
    type = Column(String, nullable=False)  # Type of the model (e.g., "mistral", "gemma")
    description = Column(String, nullable=True)  # Optional description of the model
    model_metadata = Column(String, nullable=True)  # Full ModelInfo metadata as formatted string
    quantized = Column(Integer, default=0)  # 0 = not quantized (full precision), 1 = pre-quantized (MLX)
    param_size = Column(Float, default=4)  # Model parameter size in billions (2, 4, 8, 16, etc.)
    is_attached_to_kb = Column(Integer, default=0)  # 0 or 1 Indicates if the model is attached to a knowledge base
    kb_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="SET NULL"), nullable=True)  # Foreign key to the knowledge base if attached

    kb = relationship("KnowledgeBase", back_populates="llm", uselist=False)
    conversations = relationship("Conversation", back_populates="llm", cascade="all, delete-orphan")
        
    __table_args__ = (
        {"sqlite_autoincrement": True}
    )