"""Agent system-prompt construction.

- build_agent_system_prompt: size-tier prompt (reuses prompt_utils tiers).
- build_kb_system_prompt: dedicated KB-assistant prompt (PR3, issue #81) —
  strict grounding, canonical abstention, per-source attribution, dynamic
  answer-language instruction. REPLACES the tier prompt when excerpts exist
  (the tier prompts carry anti-RAG instructions like small's "Not sure").
"""

import pytest

from src.agents.prompts import build_agent_system_prompt, build_kb_system_prompt
from src.utils.kb_utils import KbExcerpt

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


# ===================== KB-assistant prompt (PR3) =====================

EXCERPTS = [
    KbExcerpt(source_file="contrat-cadre.docx", text="Le préavis est de 90 jours."),
    KbExcerpt(source_file="faq-support.md", text="Le support répond sous 48 h."),
]


class TestBuildKbSystemPrompt:
    def _prompt(self, question="Quel est le préavis ?", **kwargs):
        return build_kb_system_prompt(
            _Llm(name="Analyste 4B"), excerpts=EXCERPTS, question=question, **kwargs
        )

    def test_strict_grounding_and_canonical_abstention(self):
        p = self._prompt()
        assert "ONLY from the document excerpts" in p
        assert "not in the documents" in p  # single canonical abstention clause
        assert "exactly as written" in p  # figures/clauses fidelity

    def test_excerpts_are_attributed_and_ordered(self):
        p = self._prompt()
        a = p.find("[Document: contrat-cadre.docx]")
        b = p.find("[Document: faq-support.md]")
        assert -1 < a < b  # both present, RRF order preserved
        assert "Le préavis est de 90 jours." in p
        assert "Le support répond sous 48 h." in p
        assert "mention the document" in p  # according-to attribution rule

    def test_language_instruction_is_dynamic_and_last(self):
        fr = self._prompt(question="Quel est le préavis de résiliation du contrat ?")
        assert fr.strip().endswith("Réponds en français.")
        en = self._prompt(question="What is the notice period for termination?")
        assert en.strip().endswith("Answer in English.")

    def test_ambiguous_question_falls_back_to_generic_language_line(self):
        p = self._prompt(question="ok")
        assert p.strip().endswith("Answer in the same language as the user's question.")

    def test_tier_anti_rag_instructions_are_gone(self):
        # The KB prompt REPLACES the tier prompt: small-tier's "Not sure"
        # eluded T7 with the answer in plain sight.
        p = self._prompt()
        assert "Not sure" not in p
        assert "8 short lines" not in p

    def test_model_name_custom_prompt_and_starred_are_kept(self):
        p = self._prompt(
            custom_prompt="Tutoie l'utilisateur",
            starred_messages=["le client est Meridia"],
        )
        assert "Analyste 4B" in p
        assert "Additional instructions: Tutoie l'utilisateur" in p
        assert "Important points" in p and "le client est Meridia" in p

    def test_closing_reminder_sandwiches_the_excerpts(self):
        # Lost-in-the-middle: instructions live at BOTH ends of the prompt.
        p = self._prompt()
        reminder = p.find("answer only from the excerpts above")
        last_excerpt = p.find("[Document: faq-support.md]")
        assert reminder > last_excerpt > -1
