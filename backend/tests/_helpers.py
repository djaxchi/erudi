"""Shared helpers for the test suite.

Currently exposes platform detection helpers used by both `conftest.py`
fixtures and per-file `pytest.mark.skipif` guards. Mirrors the dispatch
logic of `src.engines.base_engine.BaseEngine.get_engine()` without
re-evaluating it on every call site.

Imported explicitly by test files (not auto-discovered by pytest).
"""
from __future__ import annotations


def is_mlx_platform() -> bool:
    """Return True iff `BaseEngine.get_engine()` resolves to `MLX_Engine`."""
    try:
        from src.engines.base_engine import BaseEngine
        return BaseEngine.get_engine().__name__ == "MLX_Engine"
    except Exception:
        return False


def is_cuda_platform() -> bool:
    """Return True iff `BaseEngine.get_engine()` resolves to `CUDA_Engine`."""
    try:
        from src.engines.base_engine import BaseEngine
        return BaseEngine.get_engine().__name__ == "CUDA_Engine"
    except Exception:
        return False


def is_cpu_platform() -> bool:
    """Return True iff `BaseEngine.get_engine()` resolves to `CPU_Engine`."""
    try:
        from src.engines.base_engine import BaseEngine
        return BaseEngine.get_engine().__name__ == "CPU_Engine"
    except Exception:
        return False


import json
import re

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk


class ToolableFakeChatModel(GenericFakeChatModel):
    """GenericFakeChatModel usable under ``create_agent(tools=[...])``.

    Two gaps in the stock fake are filled:
    - ``bind_tools`` raises NotImplementedError → no-op here (the scripted
      messages already decide whether a tool gets called);
    - ``_stream`` only splits ``content`` and ignores modern ``tool_calls``
      (a tool-call-only message yields zero chunks → "No generations found
      in stream") → emitted as a single chunk with ``tool_call_chunks``.

    A message carrying BOTH content and ``tool_calls`` streams its content
    tokens first, THEN the ``tool_call_chunks`` chunk — mirroring the real
    pre-tool narration order observed on local models (#297).
    """

    def bind_tools(self, tools, **kwargs):
        return self

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        result = self._generate(messages, stop=stop, run_manager=None, **kwargs)
        message = result.generations[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if message.content or not tool_calls:
            tokens = re.split(r"(\s)", message.content)
            for index, token in enumerate(tokens):
                is_last = index == len(tokens) - 1 and not tool_calls
                chunk = ChatGenerationChunk(
                    message=AIMessageChunk(
                        content=token, chunk_position="last" if is_last else None
                    )
                )
                if run_manager:
                    run_manager.on_llm_new_token(token, chunk=chunk)
                yield chunk
        if tool_calls:
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    chunk_position="last",
                    tool_call_chunks=[
                        {
                            "name": call["name"],
                            "args": json.dumps(call["args"]),
                            "id": call["id"],
                            "index": index,
                            "type": "tool_call_chunk",
                        }
                        for index, call in enumerate(message.tool_calls)
                    ],
                )
            )
