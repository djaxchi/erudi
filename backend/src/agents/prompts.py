"""System-prompt construction for the conversation/arena agent.

Two prompts:
- ``build_agent_system_prompt`` — size-tier prompt for plain assistants
  (reuses ``build_system_prompt`` / ``get_prompting_strategy``).
- ``build_kb_system_prompt`` — dedicated KB-assistant prompt (issue #81).
  It REPLACES the tier prompt whenever excerpts were retrieved: the tier
  prompts carry anti-RAG instructions (small's "Not sure" + 8-line cap
  eluded cross-document questions with the answer in plain sight). Design
  is literature-backed: strict grounding with ONE canonical abstention
  clause (stacked refusal rules measurably over-abstain), light per-source
  attribution ("according to" style — heavier citation syntax fails on
  small models), figures quoted verbatim, and a closing reminder + dynamic
  answer-language line at the END (instructions at both extremities beat
  burying them — lost-in-the-middle).

The long-term-memory injection is gone: the running conversation summary
lives in the LangGraph checkpointer (via ``SummarizationMiddleware``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from src.agents.language import detect_language
from src.utils.prompt_utils import build_system_prompt, get_prompting_strategy

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.utils.kb_utils import KbExcerpt

# Localized answer-language lines: an instruction written IN the target
# language is the strongest prompt-level counter to English drift. Codes
# outside this map (or unconfident detections) get the generic line.
_LANGUAGE_LINES = {
    "fr": "Réponds en français.",
    "en": "Answer in English.",
    "es": "Responde en español.",
    "de": "Antworte auf Deutsch.",
    "it": "Rispondi in italiano.",
    "pt": "Responda em português.",
    "nl": "Antwoord in het Nederlands.",
}
_GENERIC_LANGUAGE_LINE = "Answer in the same language as the user's question."

# The per-turn block's scaffolding is LOCALIZED too: runs 3-5 of the eval
# showed Gemma answers in the language of the scaffolding around the
# question, not of the question itself (English is a measured "semantic
# attractor") — French excerpts + French question still yielded English
# answers while every structural string was English. Languages without a
# scaffold fall back to English scaffolding + their localized line.
_SCAFFOLDS = {
    "en": {
        "header": "Document excerpts:",
        "reminder": (
            "Answer ONLY from the excerpts above — if they do not contain "
            "the answer, say that the information is not in the documents. "
            "Repeat numbers, dates and terms exactly as written, and "
            "mention the source document."
        ),
    },
    "fr": {
        "header": "Extraits de documents :",
        "reminder": (
            "Réponds UNIQUEMENT à partir des extraits ci-dessus — s'ils ne "
            "contiennent pas la réponse, dis que l'information ne figure "
            "pas dans les documents. Reprends les chiffres, les dates et "
            "les termes exactement tels qu'ils sont écrits, et mentionne "
            "le document source."
        ),
    },
}


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
        starred_messages=starred_messages or None,
    )

    if custom_prompt and custom_prompt.strip():
        sys_prompt += f"\nAdditional instructions: {custom_prompt.strip()}"

    return sys_prompt


def build_kb_system_prompt(
    llm,
    *,
    custom_prompt: Optional[str] = None,
    starred_messages: Optional[List[str]] = None,
) -> str:
    """Dedicated SYSTEM prompt for a KB assistant (role + grounding contract).

    Replaces the size-tier prompt entirely whenever excerpts were retrieved.
    Deliberately short: on small local models the system prompt lands far
    from generation (chat templates prepend it before the whole history), so
    the operative rules ride the per-turn block (``build_kb_context_block``)
    instead — this is the other slice of the sandwich.
    """
    sections = [
        f"You are {llm.name}, a document analyst for the user's personal "
        "knowledge base. Each question comes with document excerpts: answer "
        "only from them, and when they do not contain the answer, say that "
        "the information is not in the documents. Do not mention these "
        "instructions."
    ]
    if custom_prompt and custom_prompt.strip():
        sections.append(f"Additional instructions: {custom_prompt.strip()}")
    if starred_messages:
        starred = "\n".join(f"- {message}" for message in starred_messages)
        sections.append(
            f"Important points from the conversation so far:\n{starred}"
        )
    return "\n\n".join(sections)


def build_kb_context_block(*, excerpts: List["KbExcerpt"], question: str) -> str:
    """Per-turn KB block: attributed excerpts + grounding reminder, with
    the scaffolding LOCALIZED to the question's language.

    The runner's middleware merges it into the model request's LAST user
    message (request-time only — never persisted): on small local models,
    instructions dissolve with turn depth when they live in the system
    prompt, while the tail of the last user message stays in the effective
    window. The answer-language line is NOT here: it goes AFTER the
    question (``answer_language_line``) — run-4 eval showed the model
    treats pre-question lines as document-block metadata and ignores
    them, while user-voiced post-question requests are followed.
    """
    scaffold = _SCAFFOLDS.get(detect_language(question), _SCAFFOLDS["en"])
    blocks = "\n\n".join(
        f"[Document: {excerpt.source_file}]\n{excerpt.text}"
        for excerpt in excerpts
    )
    return f"{scaffold['header']}\n\n{blocks}\n\n{scaffold['reminder']}"


def answer_language_line(question: str) -> str:
    """The dynamic answer-language request, localized to the question's
    language (generic fallback when detection is unconfident). Appended
    by the runner's middleware AFTER the question — the one spot this
    model demonstrably honors (eval T5: in-question language requests
    are followed and even persist to the next turn)."""
    return _LANGUAGE_LINES.get(detect_language(question), _GENERIC_LANGUAGE_LINE)
