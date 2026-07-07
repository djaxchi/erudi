"""Per-turn KB mode routing for conversation/arena (issue #84).

The KB mode is DERIVED from the model, never a user toggle:
  - KB attached & the size tier allows context & the model is tool-capable
    -> AGENTIC: the KB is exposed as the ``search_knowledge_base`` tool and the
       model decides when to consult it (no systematic injection).
  - KB attached & tier allows & NOT tool-capable -> SYSTEMATIC: today's path,
    excerpts retrieved up front and merged request-time (unchanged).
  - otherwise -> PLAIN: zero tools (#129) — plain chat never pays the
    tool-scaffolding cost, whatever the model's capability.

Factored here so conversation and arena share one decision. Retrieval is
injected as a callable so each caller keeps its own failure policy
(conversation degrades to no-context, arena raises); it is only invoked in
systematic mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from src.agents.prompts import (
    answer_language_line,
    build_agent_system_prompt,
    build_kb_agentic_system_prompt,
    build_kb_context_block,
    build_kb_system_prompt,
)
from src.core.logging import logger
from src.utils.kb_utils import KbExcerpt
from src.utils.prompt_utils import get_prompting_strategy


@dataclass(frozen=True)
class TurnPlan:
    """The runner bundle for one turn: prompt, tools, KB block, tool context."""

    system_prompt: str
    tools: list
    kb_context_block: Optional[str]
    kb_language_line: str
    context: Optional[Any]  # KbToolContext in agentic mode, else None


def _param_size(llm) -> float:
    return llm.param_size if getattr(llm, "param_size", None) is not None else 2


def should_use_kb(llm) -> bool:
    """True when the model has a KB attached AND its size tier allows context."""
    if not getattr(llm, "is_attached_to_kb", False):
        return False
    return get_prompting_strategy(_param_size(llm)).get("use_kb_context", False)


def plan_turn(
    llm,
    *,
    question: str,
    retrieve: Callable[[], List[KbExcerpt]],
    custom_prompt: Optional[str] = None,
    starred_messages: Optional[List[str]] = None,
) -> TurnPlan:
    """Decide the turn's mode and build the runner bundle.

    ``retrieve`` is only called in systematic mode: agentic mode defers
    retrieval to the model's tool call, and plain mode has no KB.
    """
    # Deferred (#160): importing the tools module pulls the LangChain ``@tool``
    # machinery, needed on turns only — never at boot. Deterministic tools are
    # carried by KB turns only (the KB tool is added in agentic mode); plain
    # chat is zero-tool (#129).
    from src.agents.tools import KbToolContext, calculator, search_knowledge_base

    base_tools = [calculator]

    if should_use_kb(llm) and getattr(llm, "supports_tools", False):
        budget = get_prompting_strategy(_param_size(llm))["kb_token_budget"]
        logger.info(
            f"Turn mode: agentic KB (kb_id={getattr(llm, 'kb_id', None)}, "
            f"reason=model supports tools and size tier allows KB context)"
        )
        return TurnPlan(
            system_prompt=build_kb_agentic_system_prompt(
                llm, custom_prompt=custom_prompt, starred_messages=starred_messages
            ),
            tools=[*base_tools, search_knowledge_base],
            kb_context_block=None,
            kb_language_line="",
            context=KbToolContext(kb_id=llm.kb_id, token_budget=budget),
        )

    # Systematic: retrieve() encapsulates is_attached + tier + failure policy.
    excerpts = retrieve()
    if excerpts:
        logger.info(
            f"Turn mode: systematic KB (kb_id={getattr(llm, 'kb_id', None)}, "
            f"excerpts={len(excerpts)}, reason=KB attached, tier allows context, "
            f"model lacks tool support)"
        )
        return TurnPlan(
            system_prompt=build_kb_system_prompt(
                llm, custom_prompt=custom_prompt, starred_messages=starred_messages
            ),
            tools=list(base_tools),
            kb_context_block=build_kb_context_block(excerpts=excerpts, question=question),
            kb_language_line=answer_language_line(question),
            context=None,
        )

    if not getattr(llm, "is_attached_to_kb", False):
        plain_reason = "no KB attached"
    elif not should_use_kb(llm):
        plain_reason = "size tier disables KB context"
    else:
        plain_reason = "KB retrieval returned no excerpts"
    logger.info(f"Turn mode: plain (reason={plain_reason})")
    # Zero tools in plain mode (#129): the calculator was a demo tool whose
    # scaffolding cost hurt every model (and wrecked small ones) for no product
    # value outside KB turns.
    return TurnPlan(
        system_prompt=build_agent_system_prompt(
            llm, custom_prompt=custom_prompt, starred_messages=starred_messages
        ),
        tools=[],
        kb_context_block=None,
        kb_language_line="",
        context=None,
    )
