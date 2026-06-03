"""P3 — agent system-prompt construction (reuses prompt_utils tiers, drops LTM)."""

import pytest

from src.agents.prompts import build_agent_system_prompt

pytestmark = pytest.mark.unit


class _Llm:
    def __init__(self, name="Test 7B", param_size=7.0):
        self.name = name
        self.param_size = param_size


def test_system_prompt_includes_model_name_and_drops_ltm():
    p = build_agent_system_prompt(_Llm(name="Qwen 7B", param_size=7.0))
    assert "Qwen 7B" in p
    # Long-term memory now lives in the checkpointer, never injected here.
    assert "Summary of the conversation" not in p


def test_starred_messages_injected():
    p = build_agent_system_prompt(_Llm(param_size=7.0), starred_messages=["use async def"])
    assert "Important points" in p
    assert "use async def" in p


def test_custom_prompt_appended():
    p = build_agent_system_prompt(_Llm(param_size=7.0), custom_prompt="Speak like a pirate")
    assert "Additional instructions: Speak like a pirate" in p


def test_param_size_none_falls_back():
    # m4: defensive fallback when a seeded model has no param_size.
    p = build_agent_system_prompt(_Llm(param_size=None))
    assert isinstance(p, str) and len(p) > 0
