"""Tests for the per-turn KB mode routing (issue #84, step 7).

The mode is derived from the model, never a user toggle. These cover the three
modes (plain / systematic / agentic), the NULL-capability fallback, and the
per-model verified wire routing (#298): with the tri-state flag unset, a KB
turn goes agentic iff the model declares tools (``supports_tools``) AND its
tool calls were verified to parse on this engine's wire
(``supports_tools_wire is True``).
"""
from types import SimpleNamespace

import pytest

from src.agents.kb_mode import plan_turn, should_use_kb
from src.agents.tools import calculator, search_knowledge_base
from src.core.config import parse_kb_agentic_flag
from src.utils.kb_utils import KbExcerpt

pytestmark = pytest.mark.unit


def _llm(**kw):
    base = dict(
        name="M", param_size=7.0, is_attached_to_kb=False, kb_id=None,
        supports_tools=None, supports_tools_wire=None,
    )
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
        # Flag True = force-agentic (#288-era opt-in, kept as the debug state
        # of the #298 tri-state flag): the wire capability is bypassed.
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
        # Composed prompt (#129): tier persona base + agentic KB section.
        assert "You are Erudi" in plan.system_prompt
        assert "call search_knowledge_base before answering" in plan.system_prompt

    def test_tool_capable_but_unverified_wire_defaults_to_systematic(self):
        # #298: with the flag unset (per-model routing), a model that declares
        # tools but whose wire capability is unverified (NULL) does NOT get the
        # search tool; it takes the systematic context-injection path.
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
        # Composed prompt (#129): tier persona base + systematic KB section.
        assert "You are Erudi" in plan.system_prompt
        assert "excerpts from the user's documents" in plan.system_prompt

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


class TestPerModelWireRouting:
    """#298 routing truth table.

    agentic iff should_use_kb AND (flag is True
                                   OR (flag is None AND supports_tools
                                       AND supports_tools_wire is True))
    """

    def _plan(self, monkeypatch, *, flag, tools, wire, attached=True):
        from src.core import config

        monkeypatch.setattr(config, "KB_AGENTIC_MODE", flag)
        excerpts = [KbExcerpt(source_file="d.pdf", text="x")]
        return plan_turn(
            _llm(
                is_attached_to_kb=attached, kb_id=5,
                supports_tools=tools, supports_tools_wire=wire,
            ),
            question="q", retrieve=lambda: excerpts,
        )

    def _is_agentic(self, plan):
        return plan.context is not None and search_knowledge_base in plan.tools

    # ---- flag None: per-model routing (the new default) ----

    def test_flag_none_tools_and_verified_wire_is_agentic(self, monkeypatch):
        plan = self._plan(monkeypatch, flag=None, tools=True, wire=True)
        assert self._is_agentic(plan)
        assert plan.kb_context_block is None

    def test_flag_none_wire_false_is_systematic(self, monkeypatch):
        # Verified unreliable (e.g. Llama 3.1 8B leaks raw JSON on mlx wire).
        plan = self._plan(monkeypatch, flag=None, tools=True, wire=False)
        assert not self._is_agentic(plan)
        assert plan.kb_context_block is not None

    def test_flag_none_wire_null_is_systematic(self, monkeypatch):
        # Unverified (pre-#298 rows before the backfill lands) -> systematic.
        plan = self._plan(monkeypatch, flag=None, tools=True, wire=None)
        assert not self._is_agentic(plan)
        assert plan.kb_context_block is not None

    def test_flag_none_no_tool_support_is_systematic_even_with_wire(self, monkeypatch):
        # Wire True cannot outrank the template gate: no declared tools, no agent.
        for tools in (False, None):
            plan = self._plan(monkeypatch, flag=None, tools=tools, wire=True)
            assert not self._is_agentic(plan)

    # ---- flag True: force agentic (debug) ----

    def test_flag_true_forces_agentic_whatever_the_wire(self, monkeypatch):
        for wire in (True, False, None):
            plan = self._plan(monkeypatch, flag=True, tools=True, wire=wire)
            assert self._is_agentic(plan), f"wire={wire}"

    def test_flag_true_forces_agentic_even_without_declared_tools(self, monkeypatch):
        # Debug override: the flag exists to exercise the agentic path at will.
        plan = self._plan(monkeypatch, flag=True, tools=False, wire=False)
        assert self._is_agentic(plan)

    def test_flag_true_still_requires_a_kb(self, monkeypatch):
        from src.core import config

        monkeypatch.setattr(config, "KB_AGENTIC_MODE", True)
        plan = plan_turn(
            _llm(supports_tools=True, supports_tools_wire=True),
            question="q", retrieve=lambda: [],
        )
        assert plan.tools == [] and plan.context is None  # plain mode

    # ---- flag False: kill switch ----

    def test_flag_false_forces_systematic_even_fully_verified(self, monkeypatch):
        plan = self._plan(monkeypatch, flag=False, tools=True, wire=True)
        assert not self._is_agentic(plan)
        assert plan.kb_context_block is not None


class TestKbAgenticFlagParsing:
    """Tri-state ERUDI_KB_AGENTIC parsing (#298). Unset -> None (per-model
    routing, the default); 1/true -> force agentic; 0/false -> kill switch."""

    def test_unset_is_none(self):
        assert parse_kb_agentic_flag(None) is None

    def test_truthy_values(self):
        for raw in ("1", "true", "True", "TRUE", " 1 "):
            assert parse_kb_agentic_flag(raw) is True, raw

    def test_falsy_values(self):
        for raw in ("0", "false", "False", "FALSE", " 0 "):
            assert parse_kb_agentic_flag(raw) is False, raw

    def test_empty_and_garbage_fall_back_to_per_model(self):
        for raw in ("", "  ", "yes", "on", "2"):
            assert parse_kb_agentic_flag(raw) is None, raw
