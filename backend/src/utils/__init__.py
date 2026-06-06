"""Utility Modules for Erudi Backend.

This package provides utility functions organized by domain:

Modules:
    - prompt_utils: System prompt building and prompting strategy selection
    - kb_utils: Knowledge base retrieval (rebuilt on PGVectorStore)
    - file_processor: Text processing for TRAINING datasets (KB ingestion
      lives in src.ingestion: DocumentReader → cleaning → chunking)
    - hf_model_metadata: HuggingFace model metadata fetching and formatting

Clean API Surface:
    Export commonly used functions for convenient imports while maintaining
    module organization for code clarity.

Examples:
    >>> # Direct module imports (preferred for clarity)
    >>> from src.utils.prompt_utils import build_system_prompt
    >>> from src.utils.kb_utils import get_relevant_texts_from_kb
    >>>
    >>> # Package-level imports (convenient)
    >>> from src.utils import build_system_prompt
    >>> from src.utils import get_relevant_texts_from_kb

See Also:
    - src.ingestion: KB document ingestion (extraction, chunking, embeddings)
    - src.engines: Inference engines
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

# File processing utilities (training pipeline)
from src.utils.file_processor import (
    split_sentences,
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

__all__ = [
    # Prompt utilities
    'build_system_prompt',
    'get_prompting_strategy',
    # KB utilities
    'get_relevant_texts_from_kb',
    # File processing (training)
    'split_sentences',
    'extract_text_from_pdf',
    'clean_text',
    'chunk_text',
    'process_pdfs_to_causal_dataset',
    # HF metadata
    'get_disk_size_after_quant',
    'get_model_size_estimate',
    'get_parameter_count_from_name',
    'format_model_info_metadata',
]
