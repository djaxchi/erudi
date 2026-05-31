"""P3 — AgentRunner: happy path, multi-turn persistence, arena mode, error policy.

Uses a real ``GenericFakeChatModel`` (not an AsyncMock — ``create_agent``
validates the model type and runs it through the LangGraph runtime) injected by
patching ``build_chat_model``. The engine is a bare ``BaseEngine`` subclass so
``generation_guard`` works without spawning a real model.
"""

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.agents import runner as runner_module
from src.agents.model_factory import build_chat_model
from src.agents.runner import AgentRunner, GenParams, ERROR_SENTINEL
from src.core import config
from src.engines.base_engine import BaseEngine

pytestmark = pytest.mark.unit


class _FakeEngine(BaseEngine):
    """Supplies generation_guard without touching real engine state."""


class _Llm:
    id = 7
    link = "/fake/path"
    name = "Test 7B"
    param_size = 7.0


_PARAMS = GenParams(temperature=0.5, top_p=0.9, max_tokens=64)


@pytest.fixture(autouse=True)
def _engine(monkeypatch):
    monkeypatch.setattr(config, "LLM_Engine", _FakeEngine)
    yield
    _FakeEngine._last_used = None


def _patch_model(monkeypatch, fake_model):
    monkeypatch.setattr(runner_module, "build_chat_model", lambda llm, **kw: fake_model)


async def test_astream_yields_raw_token_text(monkeypatch):
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="Python is awesome")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())
    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="hi", system_prompt="sys",
            params=_PARAMS, thread_id="c1", summarize=False,
        )
    ]
    # raw concatenation of token text (the text/plain wire contract)
    assert "".join(out) == "Python is awesome"


async def test_multi_turn_restores_context_from_checkpointer(monkeypatch):
    fake = GenericFakeChatModel(
        messages=iter([AIMessage(content="first"), AIMessage(content="second")])
    )
    _patch_model(monkeypatch, fake)
    cp = InMemorySaver()
    runner = AgentRunner(checkpointer=cp)
    cfg = {"configurable": {"thread_id": "c1"}}

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="q1", system_prompt="s", params=_PARAMS, thread_id="c1"
    ):
        pass
    async for _ in runner.astream_text(
        llm=_Llm(), user_message="q2", system_prompt="s", params=_PARAMS, thread_id="c1"
    ):
        pass

    # Only the new message is sent each turn; the checkpointer restores + appends.
    probe = create_agent(GenericFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
    snap = await probe.aget_state(cfg)
    assert [m.type for m in snap.values["messages"]] == ["human", "ai", "human", "ai"]


async def test_arena_mode_runs_without_checkpointer(monkeypatch):
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="duel answer")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=None)
    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="hi", system_prompt="s",
            params=_PARAMS, thread_id=None, summarize=False,
        )
    ]
    assert "".join(out) == "duel answer"


async def test_construction_error_yields_sentinel(monkeypatch):
    def _boom(llm, **kw):
        raise RuntimeError("model load failed")

    monkeypatch.setattr(runner_module, "build_chat_model", _boom)
    runner = AgentRunner(checkpointer=InMemorySaver())
    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="hi", system_prompt="s", params=_PARAMS, thread_id="c1"
        )
    ]
    assert any(ERROR_SENTINEL in t for t in out)
    # error message must NOT leak a traceback
    assert all("Traceback" not in t for t in out)


async def test_repair_alternation_appends_ai_after_dangling_human(monkeypatch):
    # M2: a failed turn that left a dangling HumanMessage must be repaired so the
    # next turn doesn't send two consecutive user messages (local templates 400).
    cp = InMemorySaver()
    agent = create_agent(GenericFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
    cfg = {"configurable": {"thread_id": "c1"}}
    await agent.aupdate_state(cfg, {"messages": [HumanMessage("orphan question")]})
    assert (await agent.aget_state(cfg)).values["messages"][-1].type == "human"

    runner = AgentRunner(checkpointer=cp)
    await runner._repair_alternation(agent, cfg)

    msgs = (await agent.aget_state(cfg)).values["messages"]
    assert msgs[-1].type == "ai"
    assert ERROR_SENTINEL in msgs[-1].content


def test_build_middleware_returns_summarization_middleware():
    from langchain.agents.middleware import SummarizationMiddleware

    built = AgentRunner()._build_middleware(GenericFakeChatModel(messages=iter([])))
    assert len(built) == 1 and isinstance(built[0], SummarizationMiddleware)


async def test_summarization_compacts_checkpointer_state(monkeypatch):
    import itertools

    # Lower the thresholds so summarization fires within a few turns.
    monkeypatch.setattr(runner_module, "SUMMARY_TRIGGER_MESSAGES", 6)
    monkeypatch.setattr(runner_module, "SUMMARY_KEEP_MESSAGES", 2)

    def infinite():
        for i in itertools.count():
            yield AIMessage(content=f"answer {i} with several words here")

    fake = GenericFakeChatModel(messages=infinite())
    monkeypatch.setattr(runner_module, "build_chat_model", lambda llm, **kw: fake)

    cp = InMemorySaver()
    runner = AgentRunner(checkpointer=cp)
    for turn in range(5):
        async for _ in runner.astream_text(
            llm=_Llm(), user_message=f"q{turn}", system_prompt="s",
            params=_PARAMS, thread_id="c1", summarize=True,
        ):
            pass

    probe = create_agent(GenericFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
    msgs = (await probe.aget_state({"configurable": {"thread_id": "c1"}})).values["messages"]
    # 5 turns = 10 messages un-summarized; compaction keeps the agent context bounded.
    assert len(msgs) < 10
    assert any("summary of the conversation" in m.content.lower() for m in msgs)


def test_build_chat_model_uses_engine_handle(monkeypatch):
    # build_chat_model must point ChatOpenAI at the engine base_url and use the
    # engine's _payload_model_value (MLX sentinel), not handle["alias"].
    class _Engine:
        @staticmethod
        def get_model_and_tokenizer(llm_id, link):
            return ({"base_url": "http://127.0.0.1:8080", "alias": f"erudi-{llm_id}"}, {})

        @staticmethod
        def _payload_model_value(handle):
            return "default_model"  # MLX-style sentinel

    monkeypatch.setattr(config, "LLM_Engine", _Engine)
    chat = build_chat_model(_Llm(), temperature=0.3, top_p=0.8, max_tokens=55)
    assert chat.model_name == "default_model"
    assert chat.openai_api_base == "http://127.0.0.1:8080/v1"
    assert chat.temperature == 0.3
