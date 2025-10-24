"""Utility Modules for Erudi Backend.

This package provides utility functions organized by domain:

Modules:
    - prompt_utils: System prompt building and prompting strategy selection
    - kb_utils: Knowledge base RAG utilities for semantic search
    - file_processor: Text processing for KB and training datasets
    - hf_model_metadata: HuggingFace model metadata fetching and formatting
    - inference_utils: Backward compatibility layer (deprecated, use engines)

Clean API Surface:
    Export commonly used functions for convenient imports while maintaining
    module organization for code clarity.

Examples:
    >>> # Direct module imports (preferred for clarity)
    >>> from src.utils.prompt_utils import build_system_prompt
    >>> from src.utils.kb_utils import get_relevant_texts_from_kb
    >>> from src.utils.file_processor import prepare_for_knowledge_base
    >>> 
    >>> # Package-level imports (convenient)
    >>> from src.utils import build_system_prompt
    >>> from src.utils import get_relevant_texts_from_kb
    >>> from src.utils import prepare_for_knowledge_base

Migration Notes:
    - EmbedderService moved to src.engines.embedder_engine.Embedder_Engine
    - inference_utils.py maintained for backward compatibility only
    - Use src.engines.embedder_engine for new code

See Also:
    - src.engines: Inference engines (LLM, embedder)
    - src.domains: Business logic using utils
    - src.core: Configuration, logging, exceptions
"""

# Prompt utilities
from src.utils.prompt_utils import (
    build_system_prompt,
    get_prompting_strategy,
)

# Knowledge base utilities
from src.utils.kb_utils import (
    get_relevant_texts_from_kb,
)

# File processing utilities
from src.utils.file_processor import (
    split_sentences,
    chunk_by_tokens,
    prepare_for_knowledge_base,
    extract_text_from_pdf,
    clean_text,
    chunk_text,
    process_pdfs_to_causal_dataset,
)

# HuggingFace model metadata utilities
from src.utils.hf_model_metadata import (
    get_disk_size_after_quant,
    get_model_size_estimate,
    get_parameter_count_from_name,
    format_model_info_metadata,
)

# Backward compatibility (deprecated - use src.engines.embedder_engine)
from src.utils.inference_utils import (
    EmbedderService,  # Alias for Embedder_Engine
)

__all__ = [
    # Prompt utilities
    'build_system_prompt',
    'get_prompting_strategy',
    # KB utilities
    'get_relevant_texts_from_kb',
    # File processing
    'split_sentences',
    'chunk_by_tokens',
    'prepare_for_knowledge_base',
    'extract_text_from_pdf',
    'clean_text',
    'chunk_text',
    'process_pdfs_to_causal_dataset',
    # HF metadata
    'get_disk_size_after_quant',
    'get_model_size_estimate',
    'get_parameter_count_from_name',
    'format_model_info_metadata',
    # Deprecated (backward compatibility)
    'EmbedderService',
]
