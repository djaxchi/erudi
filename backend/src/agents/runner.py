"""AgentRunner — the shared conversation/arena streaming primitive.

One ``create_agent`` per turn, streamed as raw token text so the existing
``StreamingResponse(media_type="text/plain")`` contract (the frontend reads a
raw byte stream, no SSE framing) is preserved byte-for-byte.

  - Conversation: ``thread_id`` set + ``summarize=True`` + a checkpointer →
    history is restored from the checkpointer (only the new message is sent),
    and old turns are summarized in the agent state.
  - Arena: ``thread_id=None`` + ``summarize=False`` + no checkpointer → a
    stateless single-model call.

Everything runs inside ``engine.generation_guard()`` so model resolution + the
whole stream serialize on the single-model engine and the idle-cleanup monitor
never reaps the model mid-stream.

LangChain imports are deferred to the methods that use them (issue #160):
this module is imported at boot by the conversation/arena services, but the
agent stack is only needed on the FIRST turn, so keeping the imports
function-scoped keeps ``import src.main`` fast. ``build_chat_model`` stays a
module-level name — tests monkeypatch ``runner.build_chat_model`` — and is
itself LangChain-free at import time (``ChatOpenAI`` is deferred inside it).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from fastapi.concurrency import run_in_threadpool

from src.agents.model_factory import build_chat_model
from src.core import config
from src.core.exceptions import EngineException
from src.core.logging import logger

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


# Auto-summarization thresholds (message-count based — token triggers need a
# model profile the local server doesn't expose). Once a conversation's agent
# state exceeds the trigger, older turns are summarized by the same local model
# and replaced in the checkpointer state; the Message table keeps the full
# history for display.
SUMMARY_TRIGGER_MESSAGES = 20
SUMMARY_KEEP_MESSAGES = 10

# Frontend detects this prefix (substring match) to render an error turn in red.
# Keep it; the message intentionally carries NO traceback (avoids info leak).
ERROR_SENTINEL = "[ERROR_MESSAGE_SYSTEM]"
ERROR_MESSAGE = (
    f"{ERROR_SENTINEL} I apologize, but I encountered an error while generating "
    "a response. Please try asking your question again."
)

# Prepended (and persisted with the assistant message) by the conversation and
# arena services when the CURRENT turn carries images but the model is not
# positively vision-capable (#212): ``_StripImagesForTextModel`` drops the image
# parts, and the user is told explicitly instead of silently. Markdown italics —
# the frontend renders streamed answers as markdown.
IMAGES_IGNORED_NOTICE = "*This model doesn't support images — your image was ignored.*\n\n"


def _construction_error_message(exc: Exception) -> str:
    """Curated, traceback-free error turn for a failed agent construction.

    Agent construction is where the model is loaded (``build_chat_model`` ->
    ``engine.get_model_and_tokenizer``). When that load fails with an
    ``EngineException`` -- a specific, already-curated diagnostic like a missing
    model folder, no ``.gguf`` found, a corrupt GGUF, or a child server that
    died on spawn (#88) -- surface its message so the user learns what is
    actually wrong and can act (re-download / pick another model). Any other
    failure keeps the generic message. Neither path leaks a traceback:
    ``EngineException`` messages are hand-written, not stringified stack traces.
    """
    if isinstance(exc, EngineException):
        return f"{ERROR_SENTINEL} {exc}"
    return ERROR_MESSAGE


@dataclass
class GenParams:
    """Per-request generation parameters (resolved from payload-or-conversation)."""

    temperature: float
    top_p: float
    max_tokens: int


class AgentRunner:
    """Streams an agent turn as raw token text. Shared by conversation and arena.

    Pass a ``checkpointer`` (the app-wide ``AsyncPostgresSaver``) for stateful
    conversations; arena constructs it with ``checkpointer=None``.
    """

    def __init__(self, checkpointer: Optional[BaseCheckpointSaver] = None):
        self.checkpointer = checkpointer

    async def astream_text(
        self,
        *,
        llm,
        user_message: str | list,
        system_prompt: str,
        params: GenParams,
        thread_id: Optional[str] = None,
        summarize: bool = False,
        kb_context_block: Optional[str] = None,
        kb_language_line: str = "",
        tools: Optional[list] = None,
        context: Optional[Any] = None,
        supports_vision: Optional[bool] = None,
    ) -> AsyncIterator[str]:
        # Deferred (#160): first turn pays the agent-stack import, boot doesn't.
        from langchain.agents import create_agent
        from langchain_core.messages import HumanMessage

        from src.agents.middleware import _KbContextMiddleware, _StripImagesForTextModel

        engine = config.LLM_Engine
        stateful = thread_id is not None and self.checkpointer is not None
        run_config = {"configurable": {"thread_id": thread_id}} if stateful else {}

        async with engine.generation_guard():
            try:
                model = await run_in_threadpool(
                    build_chat_model,
                    llm,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    max_tokens=params.max_tokens,
                )
                middleware = self._build_middleware(model) if summarize else []
                if kb_context_block:
                    # After summarization: the merge must see the final
                    # message list that actually reaches the model.
                    middleware = [
                        *middleware,
                        _KbContextMiddleware(kb_context_block, kb_language_line),
                    ]
                if supports_vision is not True:
                    # Unless the model is POSITIVELY vision-capable, strip images
                    # (#212): unknown capability (None) is treated like False, so
                    # a maybe-text-only model never breaks on an attachment (the
                    # services prepend a user-facing notice). Outermost, so images
                    # are gone before the KB merge re-reads the last user message.
                    middleware = [_StripImagesForTextModel(), *middleware]
                # No implicit tools (#129): callers own the tool list (built by
                # ``plan_turn``); ``tools=None`` means a zero-tool agent.
                effective_tools = tools if tools is not None else []
                agent = create_agent(
                    model,
                    tools=effective_tools,
                    system_prompt=system_prompt,
                    checkpointer=self.checkpointer if stateful else None,
                    middleware=middleware,
                    context_schema=type(context) if context is not None else None,
                )
                logger.info(
                    f"Agent built: llm={getattr(llm, 'id', '?')} "
                    f"({getattr(llm, 'name', '?')}), "
                    f"tools={[getattr(t, 'name', str(t)) for t in effective_tools]}, "
                    f"stateful={stateful}, summarize={summarize}, "
                    f"kb_context={'yes' if kb_context_block else 'no'}"
                )
            except Exception as exc:
                logger.exception("Agent construction failed")
                yield _construction_error_message(exc)
                return

            # Aggregate-only stream accounting (never log per token): start,
            # first-token latency, then one completion line with totals.
            stream_start_s = time.perf_counter()
            first_token_s: Optional[float] = None
            chunk_count = 0
            char_count = 0
            logger.info(
                f"Agent stream started: llm={getattr(llm, 'id', '?')}, "
                f"thread_id={thread_id}"
            )
            try:
                async for token, meta in agent.astream(
                    {"messages": [HumanMessage(user_message)]},
                    config=run_config,
                    context=context,
                    stream_mode="messages",
                ):
                    if meta.get("langgraph_node") == "model" and getattr(token, "text", ""):
                        if first_token_s is None:
                            first_token_s = time.perf_counter()
                            logger.info(
                                f"Agent first token: llm={getattr(llm, 'id', '?')}, "
                                f"latency_ms={(first_token_s - stream_start_s) * 1000:.0f}"
                            )
                        chunk_count += 1
                        char_count += len(token.text)
                        yield token.text
                duration_ms = (time.perf_counter() - stream_start_s) * 1000
                logger.info(
                    f"Agent stream completed: llm={getattr(llm, 'id', '?')}, "
                    f"duration_ms={duration_ms:.0f}, chunks={chunk_count} (~tokens), "
                    f"chars={char_count}"
                )
            except Exception:
                logger.exception("Agent streaming failed")
                if stateful:
                    await self._repair_alternation(agent, run_config)
                yield ERROR_MESSAGE

    async def astream_oneshot(
        self,
        *,
        llm,
        prompt_text: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Stateless one-shot stream (no agent/checkpointer), e.g. title generation.

        Still routed through ``engine.generation_guard`` so it serializes with
        conversation/arena generations and keeps the model pinned while streaming.
        Failures are swallowed (the caller falls back to a default).
        """
        from langchain_core.messages import HumanMessage

        engine = config.LLM_Engine
        async with engine.generation_guard():
            try:
                model = await run_in_threadpool(
                    build_chat_model,
                    llm,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                )
            except Exception:
                logger.exception("One-shot model construction failed")
                return
            try:
                async for chunk in model.astream([HumanMessage(prompt_text)]):
                    text = getattr(chunk, "text", "")
                    if text:
                        yield text
            except Exception:
                logger.exception("One-shot streaming failed")
                return

    def _build_middleware(self, model):
        """Auto-summarization using the SAME local model, triggered by message count.

        The middleware rewrites the checkpointer state (drops old turns, inserts a
        summary) so the agent's context stays bounded; the Message table is
        untouched, so the UI still shows the full conversation.
        """
        from langchain.agents.middleware import SummarizationMiddleware
        from langchain_core.messages.utils import count_tokens_approximately

        from src.agents.middleware import (
            _StripStaleImagesMiddleware,
            _StripStaleKbToolMessages,
        )

        return [
            _StripStaleImagesMiddleware(),
            _StripStaleKbToolMessages(),
            SummarizationMiddleware(
                model=model,
                trigger=("messages", SUMMARY_TRIGGER_MESSAGES),
                keep=("messages", SUMMARY_KEEP_MESSAGES),
                token_counter=count_tokens_approximately,
            ),
        ]

    async def _repair_alternation(self, agent, run_config) -> None:
        """Preserve role alternation in the checkpointer after a failed turn.

        If the failed super-step left a dangling ``HumanMessage`` as the last
        message, the next turn would send two consecutive user messages and the
        local chat template would 400 ("roles must alternate"). Append an error
        ``AIMessage`` so the thread stays well-formed. If the super-step never
        committed (last message is not a human, or state is empty), do nothing.
        """
        from langchain_core.messages import AIMessage

        try:
            state = await agent.aget_state(run_config)
            messages = (state.values or {}).get("messages", []) if state else []
            if messages and messages[-1].type == "human":
                # as_node="model" is required: updating a non-empty thread is
                # otherwise "ambiguous". "model" is the create_agent node name.
                await agent.aupdate_state(
                    run_config,
                    {"messages": [AIMessage(content=ERROR_MESSAGE)]},
                    as_node="model",
                )
        except Exception:
            logger.exception("Failed to repair conversation alternation after error")
