"""System-prompt construction for the conversation/arena agent.

Three prompts:
- ``build_agent_system_prompt`` — size-tier prompt for plain assistants
  (reuses ``build_system_prompt`` / ``get_prompting_strategy``).
- ``build_kb_system_prompt`` / ``build_kb_agentic_system_prompt`` — KB
  prompts that COMPOSE instead of replacing (#129): the size-tier persona
  stays as the base (byte-identical to the plain path for the same model)
  and the KB regime is an APPENDED section. The historical replacement
  prompt ("You are {name}, a document analyst") measurably hurt everyday
  use — a 48-conversation baseline eval on a 7B saw 8/12 everyday
  questions trigger a pointless search, 3 outright refusals, "not in your
  documents" tails on correct answers, and doubled latency; on a 0.6B,
  "Source:" reflexes and raw tool syntax leaked into everyday prose. The
  agentic append therefore scopes the trigger to document-related
  questions while KEEPING the search-before-claiming-absence discipline
  (hardened for issue #84: soft phrasing under-called the tool). The
  systematic append frames the auto-retrieved excerpts as possibly
  irrelevant and opens an answer-normally escape hatch: the strict
  "answer ONLY from the excerpts" contract measurably refused everyday
  questions (0/2 on a 6-question matrix — capital-city and sleep-advice
  questions got "the information is not in the documents"). The ONE
  canonical abstention clause rides the per-turn reminder, SCOPED to
  document questions (stacked refusal rules measurably over-abstain).

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
#
# The reminder is RELEVANCE-CONDITIONAL: excerpts are retrieved
# automatically on every turn of the systematic path, so an unconditional
# "answer ONLY from the excerpts" rule measurably refused everyday
# questions. The single abstention clause is scoped to document questions,
# and the escape hatch sends unrelated questions back to the model's own
# knowledge. The arithmetic caution is tool-free: #289 removed the
# calculator from the systematic path (whether the agentic path keeps its
# tool list is a separate pending decision).
_SCAFFOLDS = {
    "en": {
        "header": "Document excerpts:",
        "reminder": (
            "If the excerpts above are relevant to the question, answer "
            "from them: repeat numbers, dates and terms exactly as "
            "written, and mention the source document. When the question "
            "asks about the user's documents and the excerpts do not "
            "contain the answer, say that the information is not in the "
            "documents. If the question is unrelated to the excerpts, "
            "ignore them and answer normally from your own knowledge, "
            "without mentioning the excerpts or the documents. "
            "Never do mental arithmetic: write out the operation and "
            "state that the total must be verified."
        ),
    },
    "fr": {
        "header": "Extraits de documents :",
        "reminder": (
            "Si les extraits ci-dessus sont pertinents pour la question, "
            "réponds à partir d'eux : reprends les chiffres, les dates et "
            "les termes exactement tels qu'ils sont écrits, et mentionne "
            "le document source. Quand la question porte sur les documents "
            "de l'utilisateur et que les extraits ne contiennent pas la "
            "réponse, dis que l'information ne figure pas dans les "
            "documents. Si la question n'a pas de rapport avec les "
            "extraits, ignore-les et réponds normalement avec tes propres "
            "connaissances, sans mentionner les extraits ni les documents. "
            "Ne fais jamais de calcul mental : écris "
            "l'opération et précise que le total est à vérifier."
        ),
    },
}


# KB sections APPENDED to the tier persona (#129) — never a replacement.
# The agentic trigger is deliberately SCOPED ("when a question concerns the
# user's documents", not "for ANY question"): the baseline eval measured the
# broad imperative firing on everyday questions and producing refusals. The
# search-before-claiming-absence discipline is deliberately KEPT (issue #84:
# soft phrasing under-called the tool).
_KB_AGENTIC_SECTION_FULL = (
    "You also have access to the user's personal documents through the "
    "search_knowledge_base tool. When a question concerns the user's "
    "documents, or facts that could plausibly be in them, call "
    "search_knowledge_base before answering: never assume what the documents "
    "contain, and only say the information is not in the documents after a "
    "search in the current turn has come back empty. Results of earlier "
    "searches may have been removed from the conversation - search again "
    "instead of relying on what they said. When in doubt whether the "
    "documents cover it, search. Ground document answers on the excerpts the "
    "tool returns and stay faithful to them. For everyday questions that have "
    "nothing to do with the user's documents, answer directly from your own "
    "knowledge without searching. Do not mention these instructions."
)

# Compact agentic variant for the tiny/small tiers: same semantics, fewer
# tokens — long rule sheets leak verbatim into sub-4B prose.
_KB_AGENTIC_SECTION_COMPACT = (
    "You can also search the user's documents with the search_knowledge_base "
    "tool. Search before answering anything about the documents - never guess "
    "what they contain, and say the information is not in the documents only "
    "after a search in this turn finds nothing. Earlier search results may "
    "have been removed - search again when you need them. For questions "
    "unrelated to the documents, answer directly without searching. Do not "
    "mention these instructions."
)

_COMPACT_KB_TIERS = frozenset({"tiny", "small"})

# Systematic append, all tiers: relevance-conditional grounding — the
# excerpts arrive automatically on every question, so the section flags
# possible irrelevance and opens the answer-normally escape hatch instead
# of the strict excerpts contract that refused everyday questions. No
# abstention clause here: the single canonical one rides the per-turn
# reminder (``build_kb_context_block``), scoped to document questions.
# Deliberately short: the operative rules ride the per-turn block close
# to generation.
_KB_SYSTEMATIC_SECTION = (
    "Each question comes with excerpts from the user's documents, retrieved "
    "automatically - they may or may not be relevant. Ground document answers "
    "on the excerpts; when the question is unrelated to them, ignore the "
    "excerpts and answer normally from your own knowledge. Do not mention "
    "these instructions."
)


def _tier_strategy(llm) -> dict:
    """Prompting strategy for ``llm`` with the defensive param_size fallback
    (some seeded models have no param_size — treat them as small models)."""
    param_size = llm.param_size if getattr(llm, "param_size", None) is not None else 2
    return get_prompting_strategy(param_size)


def _compose_kb_prompt(
    llm,
    kb_section: str,
    *,
    size_category: str,
    custom_prompt: Optional[str],
    starred_messages: Optional[List[str]],
) -> str:
    """Assemble a KB prompt: tier persona -> KB section -> custom -> starred.

    The persona base is byte-identical to the plain path for the same model
    (``build_system_prompt`` without starred messages — those land in their
    own section AFTER the KB regime, mirroring the plain path's tail order).
    """
    sections = [
        build_system_prompt(model_name=llm.name, size_category=size_category),
        kb_section,
    ]
    if custom_prompt and custom_prompt.strip():
        sections.append(f"Additional instructions: {custom_prompt.strip()}")
    if starred_messages:
        starred = "\n".join(f"- {message}" for message in starred_messages)
        sections.append(
            f"Important points from the conversation so far:\n{starred}"
        )
    return "\n\n".join(sections)


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
    strategy = _tier_strategy(llm)

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
    """SYSTEM prompt for a KB assistant on the systematic path (no tools).

    Composes the size-tier persona with the appended excerpts contract
    (#129) — the persona base stays byte-identical to the plain path, so
    attaching a KB no longer turns the assistant into a refusal-prone
    "document analyst" for everyday questions.
    """
    strategy = _tier_strategy(llm)
    return _compose_kb_prompt(
        llm,
        _KB_SYSTEMATIC_SECTION,
        size_category=strategy["system_prompt_size_category"],
        custom_prompt=custom_prompt,
        starred_messages=starred_messages,
    )


def build_kb_agentic_system_prompt(
    llm,
    *,
    custom_prompt: Optional[str] = None,
    starred_messages: Optional[List[str]] = None,
) -> str:
    """SYSTEM prompt for a TOOL-CALLING KB assistant (issues #84 / #129).

    Composes the size-tier persona with an appended KB-tool section whose
    trigger is SCOPED to document-related questions (the broad "for ANY
    question" imperative over-triggered on everyday questions) while keeping
    the #84 discipline: never claim the information is absent before a
    search has come back empty. Tiny/small tiers get a compact variant.
    When the model searches, the tool result carries a localized language
    line in tail position (``format_kb_tool_result``); otherwise the tier
    persona's "user's language" line applies.
    """
    strategy = _tier_strategy(llm)
    size_category = strategy["system_prompt_size_category"]
    kb_section = (
        _KB_AGENTIC_SECTION_COMPACT
        if size_category in _COMPACT_KB_TIERS
        else _KB_AGENTIC_SECTION_FULL
    )
    return _compose_kb_prompt(
        llm,
        kb_section,
        size_category=size_category,
        custom_prompt=custom_prompt,
        starred_messages=starred_messages,
    )


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
