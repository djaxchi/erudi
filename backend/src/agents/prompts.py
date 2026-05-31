"""System-prompt construction for the conversation/arena agent.

Reuses the existing size-adaptive prompt tiers (``build_system_prompt``) and
strategy selection (``get_prompting_strategy``), but drops the long-term-memory
injection: the running conversation summary now lives in the LangGraph
checkpointer (via ``SummarizationMiddleware``), no longer in the system prompt.
"""

from __future__ import annotations

from typing import List, Optional

from src.utils.prompt_utils import build_system_prompt, get_prompting_strategy


def build_agent_system_prompt(
    llm,
    *,
    starred_messages: Optional[List[str]] = None,
    custom_prompt: Optional[str] = None,
) -> str:
    """Build the size-adaptive system prompt for ``llm`` as a real ``SystemMessage``.

    The old hand-rolled flow merged the system text into the first user message
    (some local models lack a system role); the OpenAI-compatible servers handle
    a proper system message per the model's chat template, so we pass it as-is.
    """
    # Defensive fallback: some seeded models have no param_size.
    param_size = llm.param_size if getattr(llm, "param_size", None) is not None else 2
    strategy = get_prompting_strategy(param_size)

    sys_prompt = build_system_prompt(
        model_name=llm.name,
        size_category=strategy["system_prompt_size_category"],
        long_term_memory=None,  # summary now lives in the checkpointer (SummarizationMiddleware)
        starred_messages=starred_messages or None,
    )

    if custom_prompt and custom_prompt.strip():
        sys_prompt += f"\nAdditional instructions: {custom_prompt.strip()}"

    return sys_prompt
