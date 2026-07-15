"""Utility Modules for Erudi Backend.

This package provides utility functions organized by domain:

Modules:
    - prompt_utils: System prompt building and prompting strategy selection
    - kb_utils: Knowledge base retrieval (rebuilt on PGVectorStore)
    - hf_model_metadata: HuggingFace model metadata fetching and formatting

Boot-cost constraint (#160):
    Importing ANY ``src.utils.*`` submodule runs this package ``__init__``. The
    seed does exactly that at boot (``from src.utils.hf_model_metadata import ...``),
    so any eager import here is paid on every backend start. The convenience
    re-exports used to pull ``kb_utils`` -> ``src.ingestion.{chunking,vector_store}``
    -> ``langchain_postgres``/``langchain_core`` (~3.4 s measured) for callers that
    only wanted the 4 ms ``hf_model_metadata`` helpers. That structurally bypassed
    the ingestion lazy-loading work (#198).

    The re-exports are therefore resolved lazily via PEP 562 ``__getattr__``: the
    convenient ``from src.utils import <name>`` surface is preserved, but the home
    module (and its import cost) is only touched the first time a name is accessed.
    Prefer the direct submodule import when you already know where a symbol lives.

Clean API Surface:
    Export commonly used functions for convenient imports while maintaining
    module organization for code clarity.

Examples:
    >>> # Direct module imports (preferred for clarity)
    >>> from src.utils.prompt_utils import build_system_prompt
    >>> from src.utils.kb_utils import retrieve_kb_excerpts
    >>>
    >>> # Package-level imports (convenient, resolved lazily)
    >>> from src.utils import build_system_prompt
    >>> from src.utils import retrieve_kb_excerpts

See Also:
    - src.ingestion: KB document ingestion (extraction, chunking, embeddings)
    - src.engines: Inference engines
    - src.domains: Business logic using utils
    - src.core: Configuration, logging, exceptions
"""

from importlib import import_module
from typing import Any

# Maps each public name to the submodule that defines it. Kept as data so the
# home module is imported on first access only (PEP 562), never at package init.
_LAZY_EXPORTS = {
    # Prompt utilities
    "build_system_prompt": "src.utils.prompt_utils",
    "get_prompting_strategy": "src.utils.prompt_utils",
    # KB utilities (pull the ingestion import tree — deferred on purpose, #160)
    "KbExcerpt": "src.utils.kb_utils",
    "retrieve_kb_excerpts": "src.utils.kb_utils",
    # HF metadata
    "get_disk_size_after_quant": "src.utils.hf_model_metadata",
    "get_model_size_estimate": "src.utils.hf_model_metadata",
    "get_parameter_count_from_name": "src.utils.hf_model_metadata",
    "format_model_info_metadata": "src.utils.hf_model_metadata",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve a documented export from its home module on first access (PEP 562).

    Raises AttributeError for unknown names so the package behaves like any
    other module (and ``hasattr`` / ``from src.utils import x`` fail cleanly).
    """
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_path), name)
    globals()[name] = value  # cache so subsequent lookups skip __getattr__
    return value


def __dir__() -> list[str]:
    return sorted(list(globals()) + __all__)
