"""Agent system-prompt construction.

- build_agent_system_prompt: size-tier prompt (reuses prompt_utils tiers).
- build_kb_system_prompt: dedicated KB-assistant SYSTEM prompt (PR3,
  issue #81) — short role + grounding contract. REPLACES the tier prompt
  when excerpts exist (the tier prompts carry anti-RAG instructions like
  small's "Not sure").
- build_kb_context_block: the PER-TURN block (excerpts + grounding
  reminder + dynamic answer-language line) that the runner's middleware
  merges into the model request's last user message — system instructions
  dissolve over turn depth on small local models, the block stays glued
  to generation.
"""

import pytest

from src.agents.prompts import (
    answer_language_line,
    build_agent_system_prompt,
    build_kb_context_block,
    build_kb_system_prompt,
)
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


# ===================== KB-assistant prompts (PR3) =====================

EXCERPTS = [
    KbExcerpt(source_file="contrat-cadre.docx", text="Le préavis est de 90 jours."),
    KbExcerpt(source_file="faq-support.md", text="Le support répond sous 48 h."),
]


class TestBuildKbSystemPrompt:
    def _prompt(self, **kwargs):
        return build_kb_system_prompt(_Llm(name="Analyste 4B"), **kwargs)

    def test_role_and_grounding_contract(self):
        p = self._prompt()
        assert "Analyste 4B" in p
        assert "document analyst" in p
        assert "not in the documents" in p  # canonical abstention clause

    def test_tier_anti_rag_instructions_are_gone(self):
        # The KB prompt REPLACES the tier prompt: small-tier's "Not sure"
        # eluded T7 with the answer in plain sight.
        p = self._prompt()
        assert "Not sure" not in p
        assert "8 short lines" not in p

    def test_custom_prompt_and_starred_are_kept(self):
        p = self._prompt(
            custom_prompt="Tutoie l'utilisateur",
            starred_messages=["le client est Meridia"],
        )
        assert "Additional instructions: Tutoie l'utilisateur" in p
        assert "Important points" in p and "le client est Meridia" in p


class TestBuildKbContextBlock:
    def _block(self, question="What is the notice period?"):
        return build_kb_context_block(excerpts=EXCERPTS, question=question)

    def test_excerpts_are_attributed_and_ordered(self):
        b = self._block()
        a = b.find("[Document: contrat-cadre.docx]")
        z = b.find("[Document: faq-support.md]")
        assert -1 < a < z  # both present, RRF order preserved
        assert "Le préavis est de 90 jours." in b
        assert "Le support répond sous 48 h." in b

    def test_grounding_reminder_follows_the_excerpts(self):
        b = self._block()
        assert "ONLY from the excerpts above" in b
        assert "not in the documents" in b
        assert "exactly as written" in b
        assert "source document" in b  # according-to attribution
        # The reminder sits AFTER the excerpts (close to generation).
        assert b.find("ONLY from the excerpts above") > b.find("[Document: faq-support.md]")

    def test_scaffolding_is_localized_to_the_question_language(self):
        # Runs 3-5: the model answers in the language of the SCAFFOLDING
        # around the question (English attractor), so the scaffolding
        # itself must speak the question's language.
        fr = self._block(question="Quel est le préavis de résiliation du contrat ?")
        assert "Extraits de documents :" in fr
        assert "UNIQUEMENT à partir des extraits" in fr
        assert "ne figure pas dans les documents" in fr
        assert "Answer ONLY" not in fr

    def test_unmapped_language_falls_back_to_english_scaffolding(self):
        b = self._block(question="ok")  # unconfident detection
        assert "Document excerpts:" in b
        assert "ONLY from the excerpts above" in b


class TestAnswerLanguageLine:
    # The line is appended AFTER the question by the runner middleware:
    # pre-question language lines are read as block metadata and ignored
    # (run-4 eval), in-question user-voiced requests are honored (T5).
    def test_localized_to_the_question_language(self):
        assert answer_language_line(
            "Quel est le préavis de résiliation du contrat ?"
        ) == "Réponds en français."
        assert answer_language_line(
            "What is the notice period for termination?"
        ) == "Answer in English."

    def test_ambiguous_question_falls_back_to_generic_line(self):
        assert answer_language_line("ok") == (
            "Answer in the same language as the user's question."
        )
