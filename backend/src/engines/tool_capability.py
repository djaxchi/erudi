"""Static tool-calling capability detection via differential chat-template rendering.

A model supports tool calling iff rendering its chat template WITH a probe tool
differs from rendering it WITHOUT one. This is the same signal the local
inference servers read (mlx-vlm and llama.cpp both render the model's own chat
template when a request carries ``tools``), so we read it statically from the
downloaded artifact: no inference, no runtime probe, no network.

The engine-specific part is only *loading a tokenizer* from the local artifact
(MLX: HuggingFace directory; llama.cpp: a ``.gguf`` via ``gguf_file=``). The
decision below is shared and agnostic: it consumes any object exposing
``apply_chat_template``.
"""
from __future__ import annotations

from typing import Any

# A trivial conversation + one well-formed tool. Tool-aware templates branch on
# the ``tools`` variable (``{%- if tools %}`` and friends), so injecting one
# changes the rendered text; templates that ignore tools render identically.
_PROBE_MESSAGES = [{"role": "user", "content": "hello"}]
_PROBE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "erudi_capability_probe",
            "description": "probe tool used only for capability detection",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        },
    }
]


def tokenizer_declares_tools(tokenizer: Any) -> bool:
    """Return True iff ``tokenizer``'s chat template renders differently with a tool.

    Graceful by design: any failure (no chat template, a template that rejects
    the ``tools`` kwarg, a render error) yields ``False`` so the model falls back
    to the systematic KB path and the feature is never lost.
    """
    try:
        base = tokenizer.apply_chat_template(
            _PROBE_MESSAGES, add_generation_prompt=True, tokenize=False
        )
    except Exception:
        return False
    try:
        with_tools = tokenizer.apply_chat_template(
            _PROBE_MESSAGES, tools=_PROBE_TOOL, add_generation_prompt=True, tokenize=False
        )
    except Exception:
        # A template that cannot render with tools does not support them.
        return False
    return with_tools != base
