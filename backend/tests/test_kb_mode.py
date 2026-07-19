"""Tests for the per-turn KB mode routing (issue #84, step 7).

The mode is derived from the model, never a user toggle. These cover the three
modes (plain / systematic / agentic) plus the NULL-capability fallback.
"""
from types import SimpleNamespace

import pytest

from src.agents.kb_mode import plan_turn, should_use_kb
from src.agents.tools import calculator, search_knowledge_base
from src.utils.kb_utils import KbExcerpt

pytestmark = pytest.mark.unit


def _llm(**kw):
    base = dict(name="M", param_size=7.0, is_attached_to_kb=False, kb_id=None, supports_tools=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _must_not_retrieve():
    raise AssertionError("agentic mode must not retrieve up front")


class TestShouldUseKb:
    def test_false_without_kb(self):
        assert should_use_kb(_llm()) is False

    def test_true_with_kb_and_medium_tier(self):
        assert should_use_kb(_llm(is_attached_to_kb=True)) is True


class TestPlanTurn:
    def test_plain_mode_no_kb_is_zero_tool_for_tool_capable_model(self):
        # #129: plain chat (no KB attached) carries NO tools at all, even when
        # the model supports native function calling.
        plan = plan_turn(
            _llm(supports_tools=True), question="hi", retrieve=lambda: []
        )
        assert plan.tools == []
        assert plan.kb_context_block is None and plan.context is None
        assert "search_knowledge_base" not in plan.system_prompt

    def test_plain_mode_no_kb_is_zero_tool_for_non_tool_capable_model(self):
        # #129: same zero-tool policy for models without tool support.
        plan = plan_turn(
            _llm(supports_tools=False), question="hi", retrieve=lambda: []
        )
        assert plan.tools == []
        assert plan.kb_context_block is None and plan.context is None

    def test_agentic_mode_when_enabled_and_tool_capable(self, monkeypatch):
        # Agentic KB is opt-in (#288): enable the flag to exercise the branch.
        from src.core import config

        monkeypatch.setattr(config, "KB_AGENTIC_MODE", True)
        plan = plan_turn(
            _llm(is_attached_to_kb=True, kb_id=5, supports_tools=True),
            question="q", retrieve=_must_not_retrieve,
        )
        # Non-regression (#129): the agentic KB branch keeps BOTH tools.
        assert plan.tools == [calculator, search_knowledge_base]
        assert plan.context.kb_id == 5 and plan.context.token_budget == 1000
        assert plan.kb_context_block is None
        assert "MUST call" in plan.system_prompt

    def test_tool_capable_defaults_to_systematic(self):
        # #288: with agentic mode OFF (the default), a tool-capable model does
        # NOT get the unreliable search tool; it takes the systematic
        # context-injection path, which works across model families.
        excerpts = [KbExcerpt(source_file="d.pdf", text="Le preavis est de 90 jours.")]
        plan = plan_turn(
            _llm(is_attached_to_kb=True, kb_id=5, supports_tools=True),
            question="preavis ?", retrieve=lambda: excerpts,
        )
        assert plan.tools == []  # #288: systematic path is zero-tool
        assert search_knowledge_base not in plan.tools
        assert plan.context is None
        assert plan.kb_context_block and "[Document: d.pdf]" in plan.kb_context_block

    def test_systematic_mode_when_not_tool_capable(self):
        excerpts = [KbExcerpt(source_file="d.pdf", text="Le préavis est de 90 jours.")]
        plan = plan_turn(
            _llm(is_attached_to_kb=True, kb_id=5, supports_tools=False),
            question="préavis ?", retrieve=lambda: excerpts,
        )
        # #288: systematic KB is zero-tool (the calculator caused tool-JSON
        # leaks on some models and added nothing for document Q&A).
        assert plan.tools == []
        assert plan.context is None
        assert plan.kb_context_block and "[Document: d.pdf]" in plan.kb_context_block
        assert "document analyst" in plan.system_prompt

    def test_systematic_empty_pool_falls_back_to_plain(self):
        plan = plan_turn(
            _llm(is_attached_to_kb=True, kb_id=5, supports_tools=False),
            question="q", retrieve=lambda: [],
        )
        assert plan.kb_context_block is None and plan.context is None
        # The empty-pool fallback IS the plain mode: zero tools (#129).
        assert plan.tools == []

    def test_null_supports_tools_routes_systematic_never_agentic(self):
        # NULL (unknown capability) must behave like not-tool-capable.
        excerpts = [KbExcerpt(source_file="d.pdf", text="x")]
        plan = plan_turn(
            _llm(is_attached_to_kb=True, kb_id=5, supports_tools=None),
            question="q", retrieve=lambda: excerpts,
        )
        assert plan.context is None
        assert search_knowledge_base not in plan.tools
