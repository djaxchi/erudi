"""System-prompt construction + KB-retrieval sizing by model size.

Two helpers consumed by the conversation/arena agent layer:
    build_system_prompt: size-adaptive system prompt (tiny->xlarge tiers) with
        optional starred-message injection.
    get_prompting_strategy: maps a model's parameter count to a system-prompt
        tier + KB-retrieval settings.

The old multi-tier memory (short-term window, middle-term vector search,
long-term summary) is gone: conversation history and the rolling summary now
live in the LangGraph checkpointer (SummarizationMiddleware), so the only
retrieval left here is the Knowledge Base top-k.
"""
from typing import List, Optional


def build_system_prompt(
    model_name: str,
    size_category: str,
    starred_messages: Optional[List[str]] = None,
) -> str:
    """Build a size-adaptive system prompt for ``model_name``.

    Every tier carries the same Erudi persona doctrine (#129); depth grows
    with the tier. Starred messages are optionally appended as an
    "Important points" section. The old name-guessed training-cutoff dates
    are gone: a wrong date misleads worse than no date, and the guesses
    were wrong for entire families (the default said "August 2024" for
    Llama 3.1, whose real cutoff is December 2023).

    Args:
        model_name: Display name of the model (kept for API stability;
            the Erudi persona no longer embeds it).
        size_category: One of "tiny", "small", "medium", "large", "xlarge"
            (from ``get_prompting_strategy`` or chosen manually).
        starred_messages: Optional user-starred message contents, appended as a
            bullet list under "Important points from the conversation so far".

    Returns:
        The complete system prompt string.
    """
    if size_category == "tiny":
        # Descriptive persona only — validated by the #129 eval campaign:
        # on sub-1B models, mechanical rules leak verbatim into answers or
        # prime the very behavior they name ("give 3 to 6 items" produced
        # 52-item lists), while describing tone reliably shapes output.
        sys_prompt = (
            "You are Erudi, a helpful AI assistant. "
            "You answer in the user's language, clearly and directly, in "
            "well-written prose, and you stop when the point is made. "
            "You are warm but efficient, like a knowledgeable friend."
        )
    elif size_category == "small":
        # Descriptive persona — validated by the #129 eval campaign (S0/S1):
        # the old "≤ 8 short lines" cap produced telegraphic answers and the
        # literal "Not sure" phrase was parroting fuel; a 3B under this prompt
        # produced rich, structured answers that stop cleanly. KB grounding
        # does not live here (it rides the per-turn context block).
        sys_prompt = (
            "You are Erudi, a helpful AI assistant. "
            "You answer in the user's language, clearly and accurately, in "
            "well-written prose. You develop your answers with enough depth "
            "to be genuinely useful - structure with short paragraphs, and "
            "use lists only when they make things clearer. You are warm but "
            "efficient, like a knowledgeable friend, and you stop when the "
            "point is made."
        )
    elif size_category == "medium":
        # Descriptive persona — validated by the #129 eval campaign (M0/M1):
        # the ~600-token programming rule sheet cost every turn context weight
        # without measurably helping (the single conditional code sentence
        # below produced equal-or-better code answers: more fenced examples,
        # explicit O(1)/O(n) trade-offs), and everyday answers stay at the
        # M0 level. One voice across tiers; ~600 tokens saved per turn.
        # #304 pulled the epistemic caution line down from the large tier:
        # a 4B confidently invented a Nobel laureate during the 2.0.0 QA.
        sys_prompt = (
            "You are Erudi, a helpful AI assistant. "
            "You answer in the user's language, clearly and accurately, in "
            "well-written prose. You develop your answers with enough depth "
            "to be genuinely useful - structure with short paragraphs, and "
            "use lists only when they make things clearer. When you are not "
            "certain of a fact, say so rather than guessing. "
            "When the user asks for code, you write minimal, correct, runnable "
            "examples in fenced code blocks with the language tag, include the "
            "imports they need, and mention anything they must install. "
            "You are warm but efficient, like a knowledgeable friend, and you "
            "stop when the point is made."
        )
    else:  # "large" (8-16B) and "xlarge" (16B+)
        # Descriptive persona (#129, L0/L1 campaign): the old third-person rule
        # sheet ("IT IS CONCISE", name-guessed training cutoffs) leaked its
        # date framing into answers and carried wrong cutoff dates for whole
        # families. Same doctrine as the smaller tiers, extended with an
        # epistemic line an 8B+ can actually honor (nuance kept, uncertainty
        # admitted) - aimed at confident hallucinations.
        sys_prompt = (
            "You are Erudi, a helpful AI assistant. "
            "You answer in the user's language, clearly and accurately, in "
            "well-written prose. You develop your answers with enough depth "
            "to be genuinely useful - structure with short paragraphs, and "
            "use lists only when they make things clearer. When a question "
            "has real nuance, present it faithfully rather than flattening "
            "it, and when you are not certain of a fact, say so rather than "
            "guessing. When the user asks for code, you write minimal, "
            "correct, runnable examples in fenced code blocks with the "
            "language tag, include the imports they need, and mention "
            "anything they must install. You are warm but efficient, like a "
            "knowledgeable friend, and you stop when the point is made - a "
            "simple factual question deserves a direct answer, not an essay."
        )
        # xlarge (16B+) shares this prompt: untestable on the project's
        # reference hardware, so it aligns on the evaluated doctrine (one
        # voice across every tier) instead of keeping its own bullet sheet.
    
    # Add starred messages if there are any
    if starred_messages and len(starred_messages) > 0:
        starred_summary = "\n".join(f"- {msg}" for msg in starred_messages)
        sys_prompt += f"\nImportant points from the conversation so far:\n{starred_summary}"

    return sys_prompt


def get_prompting_strategy(param_size: float) -> dict:
    """Select the system-prompt tier + KB context budget for a model size.

    The KB budget is a token ceiling (e5 tokens, ~180/chunk), not a chunk
    count: the adaptive cut in ``kb_utils`` decides per-query how much of it
    to consume. Ceilings follow the measured literature (peak quality scales
    with model size; below ~3B oversized context degrades net accuracy), far
    under even pessimistic effective context windows.

    Args:
        param_size: Model parameter count in billions (e.g. 7 for a 7B model;
            floats like 1.5 are accepted).

    Returns:
        dict with the three keys read downstream:
        - ``system_prompt_size_category``: "tiny"|"small"|"medium"|"large"|"xlarge"
          (consumed by ``build_agent_system_prompt``);
        - ``use_kb_context``: whether to inject Knowledge Base chunks;
        - ``kb_token_budget``: max KB context size in e5 tokens.
    """
    # An unmeasured size (#201) is treated as a small model: the conservative
    # choice keeps the system prompt and KB budget modest rather than assuming a
    # large context a tiny model could not honor.
    if param_size is None or param_size <= 2:
        return {"system_prompt_size_category": "tiny", "use_kb_context": True, "kb_token_budget": 400}
    elif param_size <= 4:
        return {"system_prompt_size_category": "small", "use_kb_context": True, "kb_token_budget": 700}
    elif param_size < 8:
        return {"system_prompt_size_category": "medium", "use_kb_context": True, "kb_token_budget": 1000}
    elif param_size <= 16:
        return {"system_prompt_size_category": "large", "use_kb_context": True, "kb_token_budget": 1400}
    else:
        return {"system_prompt_size_category": "xlarge", "use_kb_context": True, "kb_token_budget": 2000}
