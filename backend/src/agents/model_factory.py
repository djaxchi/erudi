"""Build a ``ChatOpenAI`` pointed at the local engine's OpenAI-compatible server.

The engine (MLX/CUDA/CPU) spawns a child server and exposes its
``/v1/chat/completions`` endpoint; ``ChatOpenAI(base_url=...)`` talks to it. The
engine's own ``generate_stream``/SSE parser is bypassed on this path, but
``get_model_and_tokenizer`` is still the authority that spawns/selects the child
and hands back the ``base_url``.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from src.core import config


def build_chat_model(
    llm,
    *,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> ChatOpenAI:
    """Resolve the engine child for ``llm`` and wrap it as a ``ChatOpenAI``.

    SYNC and potentially slow: ``get_model_and_tokenizer`` spawns/probes the
    child server under the engine lock, so call this via ``run_in_threadpool``
    from async code (the agent runner does).

    The ``model`` field MUST go through the engine's ``_payload_model_value`` —
    MLX's server expects a ``"default_model"`` sentinel rather than the alias, so
    hardcoding ``handle["alias"]`` would break MLX inference.

    Params are set on the constructor (NOT via ``.bind`` — LangChain v1 rejects
    pre-bound models passed to ``create_agent``).
    """
    engine = config.LLM_Engine
    handle, _tokenizer = engine.get_model_and_tokenizer(llm.id, llm.link)
    model_field = engine._payload_model_value(handle)
    return ChatOpenAI(
        base_url=f"{handle['base_url']}/v1",
        api_key="not-needed",  # local server ignores it; explicit avoids OPENAI_API_KEY lookup
        model=model_field,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=None,       # cold model load can stall several seconds before first token
        max_retries=0,      # don't silently double-submit a slow local generation
        streaming=True,
        stream_usage=False,  # local servers may not emit usage in SSE; summarization triggers on count
    )
