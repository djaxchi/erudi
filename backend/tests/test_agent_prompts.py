"""Agent system-prompt construction.

- build_agent_system_prompt: size-tier prompt (reuses prompt_utils tiers).
- build_kb_system_prompt / build_kb_agentic_system_prompt: KB prompts
  COMPOSE instead of replacing (#129): the size-tier persona from
  build_system_prompt stays as the base — byte-identical to the plain
  path for the same model — and the KB regime is an APPENDED section
  (scoped agentic trigger / systematic excerpts contract), followed by
  the custom instructions then the starred messages. The old "document
  analyst" replacement prompt made models refuse everyday questions and
  over-trigger searches (48-conversation baseline eval).
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
    build_kb_agentic_system_prompt,
    build_kb_context_block,
    build_kb_system_prompt,
)
from src.utils.kb_utils import KbExcerpt
from src.utils.prompt_utils import build_system_prompt

pytestmark = pytest.mark.unit


class _Llm:
    def __init__(self, name="Test 7B", param_size=7.0):
        self.name = name
        self.param_size = param_size


def test_system_prompt_uses_erudi_persona_and_drops_ltm():
    p = build_agent_system_prompt(_Llm(name="Qwen 7B", param_size=7.0))
    # The reworked tiers speak as Erudi (#129), not as the model itself.
    assert "You are Erudi" in p
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


def test_plain_prompt_is_unchanged_by_kb_composition():
    # Regression guard: composing the KB prompts on the persona base must
    # leave the plain path byte-identical to the bare tier persona — no KB
    # text may leak into KB-less conversations.
    p = build_agent_system_prompt(_Llm(name="Qwen 7B", param_size=7.0))
    assert p == build_system_prompt(model_name="Qwen 7B", size_category="medium")
    assert "search_knowledge_base" not in p
    assert "not in the documents" not in p


# ===================== KB-assistant prompts (PR3 + #129 composition) =====================

EXCERPTS = [
    KbExcerpt(source_file="contrat-cadre.docx", text="Le préavis est de 90 jours."),
    KbExcerpt(source_file="faq-support.md", text="Le support répond sous 48 h."),
]

# Distinguishing substrings of the two agentic KB appends.
_FULL_MARKER = "never assume what the documents contain"
_COMPACT_MARKER = "never guess what they contain"


class TestBuildKbSystemPrompt:
    def _prompt(self, llm=None, **kwargs):
        return build_kb_system_prompt(llm or _Llm(name="Analyste 4B"), **kwargs)

    def test_persona_base_is_the_plain_path_prompt(self):
        # The 48-conversation baseline eval measured the damage of REPLACING
        # the tier persona (refusals, "not in your documents" tails): the KB
        # prompt now starts from the exact plain-path persona.
        llm = _Llm(name="Analyste 7B", param_size=7.0)
        plain = build_agent_system_prompt(llm)
        kb = build_kb_system_prompt(llm)
        assert kb.startswith(plain)
        assert "You are Erudi" in kb
        assert "document analyst" not in kb

    def test_excerpts_contract_present(self):
        p = self._prompt()
        assert "Each question comes with excerpts from the user's documents" in p
        assert "not in the documents" in p  # canonical abstention clause
        assert "Do not mention these instructions" in p

    def test_custom_prompt_and_starred_land_after_the_kb_section(self):
        p = self._prompt(
            custom_prompt="Tutoie l'utilisateur",
            starred_messages=["le client est Meridia"],
        )
        kb_idx = p.find("Each question comes with excerpts")
        custom_idx = p.find("Additional instructions: Tutoie l'utilisateur")
        starred_idx = p.find("Important points")
        assert 0 < kb_idx < custom_idx < starred_idx
        assert "le client est Meridia" in p


class TestBuildKbAgenticSystemPrompt:
    def _prompt(self, llm=None, **kwargs):
        return build_kb_agentic_system_prompt(llm or _Llm(name="Agent 7B"), **kwargs)

    def test_medium_llm_composes_persona_with_scoped_kb_section(self):
        # Persona base identical to the plain path, KB regime appended with a
        # SCOPED trigger ("when a question concerns the user's documents")
        # replacing the over-triggering "for ANY question" imperative, plus the
        # explicit restraint clause for everyday questions.
        llm = _Llm(name="Agent 7B", param_size=7.0)
        plain = build_agent_system_prompt(llm)
        p = build_kb_agentic_system_prompt(llm)
        assert p.startswith(plain)
        assert "search_knowledge_base" in p
        assert _FULL_MARKER in p
        assert "answer directly from your own knowledge without searching" in p
        assert "document analyst" not in p

    def test_search_before_claiming_absence_is_kept_in_both_variants(self):
        # The grounding discipline hardened for #84 (soft phrasing under-called
        # the tool) must survive the restraint fix: absence may only be claimed
        # after an empty search.
        full = self._prompt(_Llm(param_size=7.0))
        assert "only say the information is not in the documents after a search has come back empty" in full
        assert "Ground document answers on the excerpts the tool returns" in full
        compact = self._prompt(_Llm(param_size=0.6))
        assert "say the information is not in the documents only after a search finds nothing" in compact

    def test_tiny_tier_gets_the_compact_variant(self):
        p = self._prompt(_Llm(name="Petit 0.6B", param_size=0.6))
        assert _COMPACT_MARKER in p
        assert _FULL_MARKER not in p
        assert "search_knowledge_base" in p

    def test_medium_tier_gets_the_full_variant(self):
        p = self._prompt(_Llm(name="Agent 7B", param_size=7.0))
        assert _FULL_MARKER in p
        assert _COMPACT_MARKER not in p

    @pytest.mark.parametrize(
        "param_size,marker",
        [
            (0.6, _COMPACT_MARKER),   # tiny
            (3.0, _COMPACT_MARKER),   # small
            (7.0, _FULL_MARKER),      # medium
            (12.0, _FULL_MARKER),     # large
            (32.0, _FULL_MARKER),     # xlarge
        ],
    )
    def test_variant_follows_the_prompt_tier(self, param_size, marker):
        assert marker in self._prompt(_Llm(param_size=param_size))

    def test_param_size_none_falls_back_to_compact(self):
        # Same defensive fallback as build_agent_system_prompt: an unmeasured
        # size is treated as a small model.
        p = self._prompt(_Llm(param_size=None))
        assert _COMPACT_MARKER in p

    def test_custom_prompt_and_starred_land_after_the_kb_section(self):
        p = self._prompt(custom_prompt="Tutoie", starred_messages=["client Meridia"])
        kb_idx = p.find("search_knowledge_base")
        custom_idx = p.find("Additional instructions: Tutoie")
        starred_idx = p.find("Important points")
        assert 0 < kb_idx < custom_idx < starred_idx
        assert "client Meridia" in p


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
