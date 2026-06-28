"""SQLAlchemy entity for LLM model catalog and metadata.

This entity represents the complete lifecycle of an LLM model in Erudi:
- **Remote models**: Browsable from HuggingFace (local=0).
- **Downloading**: Temporary placeholder during download (local=2).
- **Local models**: Downloaded and ready for inference (local=1).
- **KB-attached**: Specialized assistants with Knowledge Base (is_attached_to_kb=True).

Relationships:
    - kb: One-to-one with KnowledgeBase (if is_attached_to_kb=True).

Example:
    from src.entities.Llm import Llm

    # Create remote model entry
    llm = Llm(
        name="Llama-3-8B-Instruct",
        local=0,
        link="meta-llama/Meta-Llama-3-8B-Instruct",
        type="llama",
        param_size=8.0,
        quantized=False
    )
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean
from src.database.core import Base
from sqlalchemy.orm import relationship, validates

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
        quantized: Boolean - False=not quantized (full precision), True=pre-quantized (MLX/GGUF format).
        param_size: Model size in billions of parameters (2, 4, 8, 16, 70, etc.).
        is_attached_to_kb: Boolean - False=standalone model, True=specialized KB assistant.
        kb_id: Foreign key to KnowledgeBase (if is_attached_to_kb=True).
        kb: Relationship to KnowledgeBase entity (one-to-one).

    Constraints:
        - local must be 0 (remote), 1 (local), or 2 (downloading).
        - param_size must be positive.
        - name must not be empty.

    Example:
        >>> llm = Llm(name="Qwen2.5-7B", local=1, link="backend/data/models/42", type="qwen", param_size=7.0)
        >>> db.add(llm)
        >>> db.commit()
    """
    __tablename__ = "llms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    local = Column(Integer, nullable=False)
    link = Column(String, nullable=True)
    type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    model_metadata = Column(String, nullable=True)
    quantized = Column(Boolean, default=False, nullable=False)
    # Tool-calling capability, detected once at post-download from the model's
    # chat template (#84). NULL = unknown (remote/not-yet-downloaded); the
    # agent treats NULL/False as "not tool-capable" -> systematic KB path.
    supports_tools = Column(Boolean, nullable=True)
    # Catalog classification (#86): True = curated foundation/base model (discovered
    # from a FOUNDATION_ORG, built via _create_base_llm), False = derived/community
    # quant. Drives the Base vs Community split and the "Models For You" hardware-fit
    # recommendations in the UI. Remote rows only; downloaded models (local=1) ignore it.
    is_base = Column(Boolean, default=False, nullable=False)
    # Capability category (#122): general / code / reasoning / math / vision /
    # medical / function / safety. Derived at discovery from pipeline_tag + card
    # tags + slug (see src.database.catalog_classify.categorize). Groups the
    # catalog into sections in the UI. Remote rows only; defaults to "general".
    category = Column(String, default="general", nullable=False)
    param_size = Column(Float, default=4.0, nullable=False)
    is_attached_to_kb = Column(Boolean, default=False, nullable=False)
    kb_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="SET NULL"), nullable=True)

    kb = relationship("KnowledgeBase", back_populates="llm", uselist=False)
    conversations = relationship("Conversation", back_populates="llm", cascade="all, delete-orphan")
    
    @validates('name')
    def validate_name(self, key, value):
        """Ensure name is not empty.
        
        Args:
            key: Column name being validated ('name').
            value: Proposed value for the name field.
            
        Returns:
            str: Stripped name value if valid.
            
        Raises:
            ValueError: If name is empty or whitespace-only.
        """
        if not value or not value.strip():
            raise ValueError("LLM name cannot be empty")
        return value.strip()
    
    @validates('local')
    def validate_local(self, key, value):
        """Ensure local is 0 (remote), 1 (ready), or 2 (downloading).
        
        Args:
            key: Column name being validated ('local').
            value: Proposed integer value for download state.
            
        Returns:
            int: The validated local state value.
            
        Raises:
            ValueError: If value is not 0, 1, or 2.
        """
        if value not in [0, 1, 2]:
            raise ValueError(f"Invalid local state: {value}. Must be 0 (remote), 1 (ready), or 2 (downloading)")
        return value
    
    @validates('param_size')
    def validate_param_size(self, key, value):
        """Ensure param_size is positive.
        
        Args:
            key: Column name being validated ('param_size').
            value: Proposed float value for parameter size in billions.
            
        Returns:
            float: The validated parameter size.
            
        Raises:
            ValueError: If param_size is zero or negative.
        """
        if value <= 0:
            raise ValueError(f"param_size must be positive, got {value}")
        return value
    
    @validates('type')
    def validate_type(self, key, value):
        """Ensure type is not empty.
        
        Args:
            key: Column name being validated ('type').
            value: Proposed string value for model family type.
            
        Returns:
            str: Stripped type value if valid.
            
        Raises:
            ValueError: If type is empty or whitespace-only.
        """
        if not value or not value.strip():
            raise ValueError("LLM type cannot be empty")
        return value.strip()