"""Inference Utilities - Backward Compatibility Layer.

DEPRECATED: This module is maintained for backward compatibility only.

Original Purpose:
    Previously housed EmbedderService and re-exported prompt/KB utilities.

Current Status:
    - EmbedderService → Moved to src.engines.embedder_engine.Embedder_Engine
    - Re-exports maintained for backward compatibility
    - Will be removed in future major version

Migration Guide:
    **Old imports (deprecated, will be removed):**
    ```python
    from src.utils.inference_utils import EmbedderService
    embedder = EmbedderService.get_embedder()
    EmbedderService.cleanup()
    
    from src.utils.inference_utils import build_system_prompt
    from src.utils.inference_utils import get_prompting_strategy
    from src.utils.inference_utils import get_relevant_texts_from_kb
    ```

    **New imports (preferred):**
    ```python
    # For embedder
    from src.engines.embedder_engine import Embedder_Engine
    embedder = Embedder_Engine.get_embedder()
    Embedder_Engine.cleanup()
    
    # For prompt utilities
    from src.utils.prompt_utils import build_system_prompt
    from src.utils.prompt_utils import get_prompting_strategy
    
    # For KB utilities
    from src.utils.kb_utils import get_relevant_texts_from_kb
    ```

Architecture Changes:
    The refactoring separates concerns:
    - **Engines** (`src.engines/`): Inference backends (LLM, embedder)
    - **Utils** (`src.utils/`): Pure utility functions (prompts, file processing)
    - **Domains** (`src.domains/`): Business logic using engines and utils

    EmbedderService moved to engines because it's an inference engine,
    not a general utility. This aligns with Erudi's multi-engine architecture.

Deprecation Timeline:
    - v0.1.x: Re-exports maintained (current)
    - v0.2.0: Deprecation warnings added
    - v1.0.0: This module removed

See Also:
    - src.engines.embedder_engine: New embedder location
    - src.utils.prompt_utils: Prompt building utilities
    - src.utils.kb_utils: Knowledge base utilities
"""

from src.core.logging import logger

# Log deprecation warning on import (will be enabled in v0.2.0)
# logger.warning(
#     "src.utils.inference_utils is deprecated. "
#     "Use src.engines.embedder_engine.Embedder_Engine for embedder, "
#     "src.utils.prompt_utils for prompts, and src.utils.kb_utils for KB operations."
# )

# Re-export Embedder_Engine as EmbedderService for backward compatibility
from src.engines.embedder_engine import Embedder_Engine as EmbedderService

# Re-export prompt utilities for backward compatibility
from src.utils.prompt_utils import build_system_prompt, get_prompting_strategy

# Re-export KB utilities for backward compatibility
from src.utils.kb_utils import get_relevant_texts_from_kb

__all__ = [
    'EmbedderService',  # Deprecated alias for Embedder_Engine
    'build_system_prompt',
    'get_prompting_strategy',
    'get_relevant_texts_from_kb',
]
