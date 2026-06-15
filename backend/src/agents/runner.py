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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from fastapi.concurrency import run_in_threadpool
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.agents.model_factory import build_chat_model
from src.agents.tools import calculator
from src.core import config
from src.core.logging import logger

# Deterministic tools carried by every chat/arena agent turn. Models with
# native function calling invoke them through the standard loop; models
# without (e.g. Gemma 3) never emit tool_calls — the server logs a warning
# and generation proceeds normally (probed, harmless).
AGENT_TOOLS = [calculator]

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


@dataclass
class GenParams:
    """Per-request generation parameters (resolved from payload-or-conversation)."""

    temperature: float
    top_p: float
    max_tokens: int


def _split_multimodal(content):
    """Split message content into (joined_text, image_parts).

    For plain-string content, returns (content, []). For OpenAI multimodal
    content (a list of ``{"type": "text"|"image_url", ...}`` parts), returns
    the joined text of the text parts and the list of image parts.
    """
    if isinstance(content, str):
        return content, []
    text = " ".join(
        p["text"]
        for p in content
        if isinstance(p, dict) and p.get("type") == "text" and p.get("text")
    )
    images = [p for p in content if isinstance(p, dict) and p.get("type") == "image_url"]
    return text, images


def _flatten_without_images(content) -> str:
    """Plain-text rendering of multimodal content; each image -> ``[image]``."""
    if isinstance(content, str):
        return content
    out = []
    for p in content:
        if isinstance(p, dict):
            if p.get("type") == "text" and p.get("text"):
                out.append(p["text"])
            elif p.get("type") == "image_url":
                out.append("[image]")
    return " ".join(out).strip()


class _KbContextMiddleware(AgentMiddleware):
    """Merge the per-turn KB block into the model request's LAST user message.

    Request-time only (``request.override``): the checkpointer keeps the
    clean question, so past turns never re-expose stale excerpts (no
    context pollution, no parroting fuel). Rationale: on small local
    models, grounding/language instructions dissolve with turn depth when
    they live in the system prompt (chat templates prepend it before the
    whole history) — the tail of the last user message is the one spot
    that always stays inside the effective window.

    Layout: excerpts+rules block, then the question, then the answer-
    language request LAST in the user's voice — pre-question language
    lines are ignored as block metadata (run-4 eval), in-question
    requests are honored (T5).
    """

    def __init__(self, context_block: str, language_line: str):
        super().__init__()
        self.context_block = context_block
        self.language_line = language_line

    def _merge(self, request):
        messages = list(request.messages)
        last = messages[-1]
        # No "Question:" label: any English structural string near the
        # question feeds the English attractor (run-5 eval finding).
        question_text, image_parts = _split_multimodal(last.content)
        merged_text = f"{self.context_block}\n\n{question_text}\n\n{self.language_line}"
        if image_parts:
            # Multimodal turn: merge the KB block into the text part and keep
            # the screenshot(s) attached for the VLM.
            merged = HumanMessage(
                content=[{"type": "text", "text": merged_text}, *image_parts]
            )
        else:
            merged = HumanMessage(content=merged_text)
        return request.override(messages=[*messages[:-1], merged])

    def wrap_model_call(self, request, handler):
        return handler(self._merge(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._merge(request))


class _StripStaleImagesMiddleware(AgentMiddleware):
    """Keep only the CURRENT turn's images in the model request.

    The checkpointer stores each turn's multimodal ``HumanMessage``, so without
    this every past screenshot would be re-sent on each follow-up and blow the
    (small, local) VLM context. Vision is therefore single-turn: an image is
    seen only on the turn it is sent; in later turns it collapses to an
    ``[image]`` text marker. The current turn — the last human message, even
    across tool-call loops where a ToolMessage is last — keeps its images.
    """

    def _strip(self, request):
        messages = list(request.messages)
        human_idxs = [i for i, m in enumerate(messages) if m.type == "human"]
        if not human_idxs:
            return request
        keep = human_idxs[-1]
        changed = False
        for i, m in enumerate(messages):
            if i == keep or not isinstance(m.content, list):
                continue
            messages[i] = m.model_copy(
                update={"content": _flatten_without_images(m.content)}
            )
            changed = True
        return request.override(messages=messages) if changed else request

    def wrap_model_call(self, request, handler):
        return handler(self._strip(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._strip(request))


class _StripStaleKbToolMessages(AgentMiddleware):
    """Placeholder the ``search_knowledge_base`` results of PAST turns.

    The checkpointer persists every KB ToolMessage, so without this each
    follow-up would re-send every past turn's (bulky) excerpts and re-introduce
    the multi-turn context pollution the request-time design of issue #81 had
    eliminated. The CURRENT turn's KB result stays intact (the model just
    fetched it and must read it); only past ones shrink to a short marker. We
    rewrite content only, never dropping the message, so the
    ``AIMessage(tool_calls) -> ToolMessage`` pairing the chat template requires
    stays valid. The checkpointer keeps the full result, so the UI is
    unaffected — symmetric to ``_StripStaleImagesMiddleware`` for images.
    """

    _MARKER = "[knowledge base results from an earlier turn omitted]"

    def _strip(self, request):
        messages = list(request.messages)
        human_idxs = [i for i, m in enumerate(messages) if m.type == "human"]
        if not human_idxs:
            return request
        keep = human_idxs[-1]  # last human marks the current turn; earlier = past
        changed = False
        for i, m in enumerate(messages):
            if i >= keep:
                continue
            if m.type == "tool" and getattr(m, "name", None) == "search_knowledge_base":
                messages[i] = m.model_copy(update={"content": self._MARKER})
                changed = True
        return request.override(messages=messages) if changed else request

    def wrap_model_call(self, request, handler):
        return handler(self._strip(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._strip(request))


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
    ) -> AsyncIterator[str]:
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
                agent = create_agent(
                    model,
                    tools=tools if tools is not None else AGENT_TOOLS,
                    system_prompt=system_prompt,
                    checkpointer=self.checkpointer if stateful else None,
                    middleware=middleware,
                    context_schema=type(context) if context is not None else None,
                )
            except Exception:
                logger.exception("Agent construction failed")
                yield ERROR_MESSAGE
                return

            try:
                async for token, meta in agent.astream(
                    {"messages": [HumanMessage(user_message)]},
                    config=run_config,
                    context=context,
                    stream_mode="messages",
                ):
                    if meta.get("langgraph_node") == "model" and getattr(token, "text", ""):
                        yield token.text
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
