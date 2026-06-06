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
from typing import AsyncIterator, Optional

from fastapi.concurrency import run_in_threadpool
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.agents.model_factory import build_chat_model
from src.core import config
from src.core.logging import logger

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
        user_message: str,
        system_prompt: str,
        params: GenParams,
        thread_id: Optional[str] = None,
        summarize: bool = False,
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
                agent = create_agent(
                    model,
                    tools=[],
                    system_prompt=system_prompt,
                    checkpointer=self.checkpointer if stateful else None,
                    middleware=self._build_middleware(model) if summarize else [],
                )
            except Exception:
                logger.exception("Agent construction failed")
                yield ERROR_MESSAGE
                return

            try:
                async for token, meta in agent.astream(
                    {"messages": [HumanMessage(user_message)]},
                    config=run_config,
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
            SummarizationMiddleware(
                model=model,
                trigger=("messages", SUMMARY_TRIGGER_MESSAGES),
                keep=("messages", SUMMARY_KEEP_MESSAGES),
                token_counter=count_tokens_approximately,
            )
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
