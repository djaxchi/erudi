"""Utility Modules for Erudi Backend.

This package provides utility functions organized by domain:

Modules:
    - prompt_utils: System prompt building and prompting strategy selection
    - kb_utils: Knowledge base retrieval (rebuilt on PGVectorStore)
    - hf_model_metadata: HuggingFace model metadata fetching and formatting

Clean API Surface:
    Export commonly used functions for convenient imports while maintaining
    module organization for code clarity.

Examples:
    >>> # Direct module imports (preferred for clarity)
    >>> from src.utils.prompt_utils import build_system_prompt
    >>> from src.utils.kb_utils import retrieve_kb_excerpts
    >>>
    >>> # Package-level imports (convenient)
    >>> from src.utils import build_system_prompt
    >>> from src.utils import retrieve_kb_excerpts

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
    KbExcerpt,
    retrieve_kb_excerpts,
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
    'KbExcerpt',
    'retrieve_kb_excerpts',
    # HF metadata
    'get_disk_size_after_quant',
    'get_model_size_estimate',
    'get_parameter_count_from_name',
    'format_model_info_metadata',
]
