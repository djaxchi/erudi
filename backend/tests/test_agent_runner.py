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
    # Repetition controls restored on the ChatOpenAI path (regression: tiny models
    # looped without them). Identity engine (no _translate_payload_kwargs) => HF names.
    assert chat.extra_body == {"repetition_penalty": 1.2, "repetition_context_size": 5}


def test_build_chat_model_translates_extra_body_per_engine(monkeypatch):
    # llama.cpp engines rename repetition_penalty -> repeat_penalty (and
    # repetition_context_size -> repeat_last_n). build_chat_model must route the
    # repetition controls through the engine's _translate_payload_kwargs so each
    # local server receives its own wire names in extra_body.
    class _LlamaEngine:
        @staticmethod
        def get_model_and_tokenizer(llm_id, link):
            return ({"base_url": "http://127.0.0.1:9090", "alias": f"erudi-{llm_id}"}, {})

        @staticmethod
        def _payload_model_value(handle):
            return handle["alias"]

        @staticmethod
        def _translate_payload_kwargs(kw):
            rename = {
                "repetition_penalty": "repeat_penalty",
                "repetition_context_size": "repeat_last_n",
            }
            return {rename.get(k, k): v for k, v in kw.items()}

    monkeypatch.setattr(config, "LLM_Engine", _LlamaEngine)
    chat = build_chat_model(_Llm(), temperature=0.3, top_p=0.8, max_tokens=55)
    assert chat.extra_body == {"repeat_penalty": 1.2, "repeat_last_n": 5}


# ===== Integration (IT3 / IT5 / IT11) — PR1 E2E validation, runner level =====


async def test_thread_id_isolation_no_cross_bleed(monkeypatch):
    # IT3: two conversations -> two checkpointer threads; neither leaks into the
    # other (each thread's history holds only its own user messages).
    import itertools

    def infinite():
        for i in itertools.count():
            yield AIMessage(content=f"reply {i}")

    monkeypatch.setattr(
        runner_module,
        "build_chat_model",
        lambda llm, **kw: GenericFakeChatModel(messages=infinite()),
    )
    cp = InMemorySaver()
    runner = AgentRunner(checkpointer=cp)

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="alpha", system_prompt="s", params=_PARAMS, thread_id="conv-1"
    ):
        pass
    async for _ in runner.astream_text(
        llm=_Llm(), user_message="beta", system_prompt="s", params=_PARAMS, thread_id="conv-2"
    ):
        pass

    probe = create_agent(GenericFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
    msgs_1 = (await probe.aget_state({"configurable": {"thread_id": "conv-1"}})).values["messages"]
    msgs_2 = (await probe.aget_state({"configurable": {"thread_id": "conv-2"}})).values["messages"]
    assert [m.content for m in msgs_1 if m.type == "human"] == ["alpha"]
    assert [m.content for m in msgs_2 if m.type == "human"] == ["beta"]


async def test_purged_thread_starts_fresh_no_resurrection(monkeypatch):
    # IT5 (BLOCKER B3): once a thread is purged (conversation deleted), reusing the
    # same thread_id — SQLite reuses autoincrement ids — must start a FRESH thread,
    # never resurrecting the deleted conversation's history.
    monkeypatch.setattr(
        runner_module,
        "build_chat_model",
        lambda llm, **kw: GenericFakeChatModel(
            messages=iter([AIMessage(content="a"), AIMessage(content="b")])
        ),
    )
    cp = InMemorySaver()
    runner = AgentRunner(checkpointer=cp)
    cfg = {"configurable": {"thread_id": "5"}}

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="old-secret", system_prompt="s", params=_PARAMS, thread_id="5"
    ):
        pass
    await cp.adelete_thread("5")
    assert await cp.aget_tuple(cfg) is None

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="brand-new", system_prompt="s", params=_PARAMS, thread_id="5"
    ):
        pass

    probe = create_agent(GenericFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
    msgs = (await probe.aget_state(cfg)).values["messages"]
    # Only the new turn — the deleted "old-secret" turn must NOT reappear.
    assert [m.type for m in msgs] == ["human", "ai"]
    assert [m.content for m in msgs if m.type == "human"] == ["brand-new"]


async def test_astream_holds_generation_lock_across_whole_stream(monkeypatch):
    # IT11: the runner wraps model resolution + the ENTIRE token stream in
    # engine.generation_guard, so the shared generation lock is held for every
    # token. The idle-cleanup tick takes that same lock, so it can never reap
    # the model mid-stream.
    monkeypatch.setattr(
        runner_module,
        "build_chat_model",
        lambda llm, **kw: GenericFakeChatModel(messages=iter([AIMessage(content="one two three")])),
    )
    runner = AgentRunner(checkpointer=InMemorySaver())

    observed_locked = []
    async for _ in runner.astream_text(
        llm=_Llm(), user_message="hi", system_prompt="s", params=_PARAMS, thread_id="c1"
    ):
        lock = _FakeEngine._generation_lock
        observed_locked.append(lock is not None and lock.locked())

    assert observed_locked and all(observed_locked)  # lock held for every token
    # Released once the stream completes (model reapable again).
    assert _FakeEngine._generation_lock is None or not _FakeEngine._generation_lock.locked()


# ===================== KB context middleware (PR3, issue #81) =====================

from pydantic import Field  # noqa: E402


class _RecordingModel(GenericFakeChatModel):
    """Fake model that records the exact message lists it receives."""

    received: list = Field(default_factory=list)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(list(messages))
        yield from super()._stream(messages, stop=stop, run_manager=run_manager, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


_BLOCK_1 = "[Document: a.md]\nLe préavis est de 90 jours.\n\nAnswer ONLY from the excerpts above."
_BLOCK_2 = "[Document: b.md]\nLe SLA est de 99,7 %.\n\nAnswer ONLY from the excerpts above."


async def test_kb_block_is_merged_into_the_model_request(monkeypatch):
    """The per-turn KB block rides the LAST user message of the model call
    (close to generation — system instructions dissolve over turn depth on
    small local models), with the real question kept last."""
    fake = _RecordingModel(messages=iter([AIMessage(content="90 jours.")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="Quel est le préavis ?", system_prompt="sys",
        params=_PARAMS, thread_id="c-kb", kb_context_block=_BLOCK_1,
    ):
        pass

    last_call = fake.received[-1]
    merged = last_call[-1]
    assert merged.type == "human"
    assert _BLOCK_1 in merged.text
    assert merged.text.strip().endswith("Question: Quel est le préavis ?")


async def test_kb_block_is_ephemeral_history_stays_clean(monkeypatch):
    """The merge happens in the model REQUEST only: the checkpointer keeps
    the clean question, so turn 2's history must show turn 1's question
    WITHOUT its excerpts (no context pollution, no parroting fuel)."""
    fake = _RecordingModel(
        messages=iter([AIMessage(content="r1"), AIMessage(content="r2")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="q1", system_prompt="s",
        params=_PARAMS, thread_id="c-kb2", kb_context_block=_BLOCK_1,
    ):
        pass
    async for _ in runner.astream_text(
        llm=_Llm(), user_message="q2", system_prompt="s",
        params=_PARAMS, thread_id="c-kb2", kb_context_block=_BLOCK_2,
    ):
        pass

    second_call = fake.received[-1]
    history_humans = [m for m in second_call if m.type == "human"]
    # Turn 1's question is back to its clean form in the history…
    assert history_humans[0].text == "q1"
    assert _BLOCK_1 not in "".join(m.text for m in second_call)
    # …and only the current turn carries its own fresh block.
    assert _BLOCK_2 in history_humans[-1].text
    assert history_humans[-1].text.strip().endswith("Question: q2")


async def test_no_kb_block_leaves_messages_untouched(monkeypatch):
    fake = _RecordingModel(messages=iter([AIMessage(content="hello")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="hi", system_prompt="sys",
        params=_PARAMS, thread_id="c-plain",
    ):
        pass

    assert fake.received[-1][-1].text == "hi"
