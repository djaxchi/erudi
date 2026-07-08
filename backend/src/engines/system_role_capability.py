"""Static system-role capability detection via chat-template probing.

Some chat templates reject the ``system`` role outright: Gemma's raises
``jinja2 TemplateError: System role not supported`` when a system message is
rendered, so passing our size-adaptive system prompt as a real system message
500s every turn. This module detects that statically from the model's own chat
template (the exact template the local inference server renders), so the runner
can fall back to folding the system prompt into the first user turn for models
that don't support a system role — instead of crashing on them.

Mirrors ``engines.tool_capability``: it reuses the engine's
``_load_capability_tokenizer`` seam (no new loading mechanism) and consumes any
object exposing ``apply_chat_template``. Differential by design — a template
that cannot render *at all* is not blamed on the system role.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Union

from src.core.logging import logger

# User-only vs. system+user. If the user-only render works but adding a leading
# system message breaks it, the system role is the cause (Gemma). If user-only
# already fails, the template is unrenderable for unrelated reasons and we must
# not blame the system role (so we do NOT fold — preserve pass-through).
_USER_ONLY = [{"role": "user", "content": "hi"}]
_SYSTEM_THEN_USER = [
    {"role": "system", "content": "x"},
    {"role": "user", "content": "hi"},
]


def tokenizer_supports_system_role(tokenizer: Any) -> bool:
    """Return True iff ``tokenizer``'s chat template accepts a leading system message.

    Graceful by design: returns True (assume supported, keep the current
    system-as-is behavior) unless a system message *specifically* breaks an
    otherwise-renderable template.
    """
    try:
        tokenizer.apply_chat_template(
            _USER_ONLY, add_generation_prompt=True, tokenize=False
        )
    except Exception:
        # Template can't render even the trivial case: not a system-role signal.
        return True
    try:
        tokenizer.apply_chat_template(
            _SYSTEM_THEN_USER, add_generation_prompt=True, tokenize=False
        )
    except Exception:
        return False
    return True


@lru_cache(maxsize=64)
def _cached(engine_name: str, local_path: str) -> bool:
    from src.core import config

    engine = config.LLM_Engine
    try:
        tokenizer = engine._load_capability_tokenizer(local_path)
    except Exception:
        logger.warning(
            f"[{engine_name}] system-role detection: could not load a tokenizer "
            f"for {local_path}; assuming the model supports a system role",
            exc_info=True,
        )
        return True
    if tokenizer is None:
        return True
    return tokenizer_supports_system_role(tokenizer)


def model_supports_system_role(local_path: Union[str, Path]) -> bool:
    """Whether the model at ``local_path`` accepts a system-role message.

    Cached per (engine, path): the probe loads only the tokenizer/template files
    (never the weights), and the result is stable for a given artifact, so a
    chat turn pays it at most once per model. Assumes True (pass the system
    message through) when the model cannot be probed — only a positively detected
    rejection makes the runner fold the system prompt into the first user turn.
    """
    from src.core import config

    if not local_path:
        return True
    engine = getattr(config, "LLM_Engine", None)
    engine_name = getattr(engine, "__name__", "engine") if engine else "engine"
    return _cached(engine_name, str(local_path))
