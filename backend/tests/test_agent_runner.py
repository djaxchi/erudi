"""P3 — AgentRunner: happy path, multi-turn persistence, arena mode, error policy.

Uses a real ``GenericFakeChatModel`` (not an AsyncMock — ``create_agent``
validates the model type and runs it through the LangGraph runtime) injected by
patching ``build_chat_model``. The engine is a bare ``BaseEngine`` subclass so
``generation_guard`` works without spawning a real model.
"""

import logging

import pytest
from langchain.agents import create_agent
from tests._helpers import ToolableFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.agents import runner as runner_module
from src.agents.model_factory import build_chat_model
from src.agents.runner import AgentRunner, GenParams, ERROR_SENTINEL
from src.agents.tools import calculator
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
    fake = ToolableFakeChatModel(messages=iter([AIMessage(content="Python is awesome")]))
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
    fake = ToolableFakeChatModel(
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
    probe = create_agent(ToolableFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
    snap = await probe.aget_state(cfg)
    assert [m.type for m in snap.values["messages"]] == ["human", "ai", "human", "ai"]


async def test_arena_mode_runs_without_checkpointer(monkeypatch):
    fake = ToolableFakeChatModel(messages=iter([AIMessage(content="duel answer")]))
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


async def test_tools_none_builds_zero_tool_agent(monkeypatch, caplog):
    """#129: with no explicit tools the agent is built with NO tools at all.

    Every production path goes through ``plan_turn`` and passes an explicit
    list; ``tools=None`` must not silently sneak the calculator back in."""
    fake = ToolableFakeChatModel(messages=iter([AIMessage(content="ok")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=None)

    with caplog.at_level(logging.INFO, logger="erudi"):
        async for _ in runner.astream_text(
            llm=_Llm(), user_message="hi", system_prompt="s",
            params=_PARAMS, thread_id=None, summarize=False,
        ):
            pass

    built = [r.message for r in caplog.records if "Agent built" in r.message]
    assert built, f"no 'Agent built' log found in: {[r.message for r in caplog.records]}"
    assert "tools=[]" in built[0]


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
    agent = create_agent(ToolableFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
    cfg = {"configurable": {"thread_id": "c1"}}
    await agent.aupdate_state(cfg, {"messages": [HumanMessage("orphan question")]})
    assert (await agent.aget_state(cfg)).values["messages"][-1].type == "human"

    runner = AgentRunner(checkpointer=cp)
    await runner._repair_alternation(agent, cfg)

    msgs = (await agent.aget_state(cfg)).values["messages"]
    assert msgs[-1].type == "ai"
    assert ERROR_SENTINEL in msgs[-1].content


def test_build_middleware_includes_strip_and_summarization():
    from langchain.agents.middleware import SummarizationMiddleware

    built = AgentRunner()._build_middleware(ToolableFakeChatModel(messages=iter([])))
    assert any(isinstance(m, SummarizationMiddleware) for m in built)
    assert any(type(m).__name__ == "_StripStaleImagesMiddleware" for m in built)


async def test_summarization_compacts_checkpointer_state(monkeypatch):
    import itertools

    # Lower the thresholds so summarization fires within a few turns.
    monkeypatch.setattr(runner_module, "SUMMARY_TRIGGER_MESSAGES", 6)
    monkeypatch.setattr(runner_module, "SUMMARY_KEEP_MESSAGES", 2)

    def infinite():
        for i in itertools.count():
            yield AIMessage(content=f"answer {i} with several words here")

    fake = ToolableFakeChatModel(messages=infinite())
    monkeypatch.setattr(runner_module, "build_chat_model", lambda llm, **kw: fake)

    cp = InMemorySaver()
    runner = AgentRunner(checkpointer=cp)
    for turn in range(5):
        async for _ in runner.astream_text(
            llm=_Llm(), user_message=f"q{turn}", system_prompt="s",
            params=_PARAMS, thread_id="c1", summarize=True,
        ):
            pass

    probe = create_agent(ToolableFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
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
    assert chat.extra_body == {"repetition_penalty": 1.1, "repetition_context_size": 64}


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
    assert chat.extra_body == {"repeat_penalty": 1.1, "repeat_last_n": 64}


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
        lambda llm, **kw: ToolableFakeChatModel(messages=infinite()),
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

    probe = create_agent(ToolableFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
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
        lambda llm, **kw: ToolableFakeChatModel(
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

    probe = create_agent(ToolableFakeChatModel(messages=iter([])), tools=[], checkpointer=cp)
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
        lambda llm, **kw: ToolableFakeChatModel(messages=iter([AIMessage(content="one two three")])),
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


class _RecordingModel(ToolableFakeChatModel):
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
        kb_language_line="Réponds en français.",
    ):
        pass

    last_call = fake.received[-1]
    merged = last_call[-1]
    assert merged.type == "human"
    assert _BLOCK_1 in merged.text
    assert "Quel est le préavis ?" in merged.text
    # The user-voiced language request is the LAST thing before generation
    # (no English "Question:" label — structural English feeds the drift).
    assert "Question:" not in merged.text
    assert merged.text.strip().endswith("Réponds en français.")
    assert merged.text.find("Quel est le préavis ?") < merged.text.find("Réponds en français.")


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
    assert "q2" in history_humans[-1].text


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


# ===================== Calculator tool in the agent loop (PR3) =====================


async def test_tool_call_round_trip_streams_only_final_text(monkeypatch):
    """Full agentic loop with the REAL calculator tool: the scripted model
    requests calculator(expression), the tool node executes it, and the
    model answers from the ToolMessage. The text/plain wire contract must
    only carry the FINAL answer (tool steps emit no text tokens).

    The calculator is passed explicitly (as ``plan_turn`` does on KB paths):
    since #129 there is no implicit default-tools fallback."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "calculator",
            "args": {"expression": "1240 + 1378 + 1456 + 1689"},
            "id": "call-1",
        }],
    )
    fake = _RecordingModel(
        messages=iter([tool_call_msg, AIMessage(content="Le total est 5763 k€.")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="Additionne les quatre trimestres.",
            system_prompt="sys", params=_PARAMS, thread_id="c-calc",
            tools=[calculator],
        )
    ]

    assert "".join(out) == "Le total est 5763 k€."
    # The second model call must carry the REAL tool result (5763), proof
    # the calculator executed inside the loop.
    second_call = fake.received[-1]
    tool_messages = [m for m in second_call if m.type == "tool"]
    assert tool_messages and tool_messages[-1].text == "5763"


async def test_empty_final_answer_falls_back_to_last_tool_result(monkeypatch):
    """#90: the model calls the calculator (which returns 4074), then emits an
    EMPTY final answer (the Gemma pattern: successful tool call, then a
    ``finish_reason=stop`` message with no content). The runner must fall back
    to the LAST tool result so a correct answer is still delivered/persisted
    instead of yielding nothing (which would crash the empty-content guard)."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "calculator",
            "args": {"expression": "1240 + 1378 + 1456"},
            "id": "call-1",
        }],
    )
    # Second model turn is EMPTY -> the fallback must kick in.
    fake = _RecordingModel(messages=iter([tool_call_msg, AIMessage(content="")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="1240 + 1378 + 1456 ?",
            system_prompt="sys", params=_PARAMS, thread_id="c-empty-final",
            tools=[calculator],
        )
    ]

    # The tool result (4074) is delivered as the answer, sober (no prefix/JSON).
    assert "".join(out).strip() == "4074"
    assert ERROR_SENTINEL not in "".join(out)


async def test_empty_final_answer_no_tool_yields_nothing(monkeypatch):
    """#90 boundary: an empty final answer with NO tool run this turn is a
    genuine failure — there is nothing to fall back to, so the runner must NOT
    fabricate content. Behavior is unchanged: the stream yields no text (the
    downstream empty-content guard still applies at persistence)."""
    fake = ToolableFakeChatModel(messages=iter([AIMessage(content="")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="hi", system_prompt="s",
            params=_PARAMS, thread_id="c-empty-notool", tools=[],
        )
    ]

    assert "".join(out) == ""
    assert ERROR_SENTINEL not in "".join(out)


async def test_non_empty_final_with_tool_does_not_append_tool_result(monkeypatch):
    """#90 guard: when the model DOES produce a real final answer after a tool
    call, the fallback must not fire — the raw tool result is never appended to
    a valid answer."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "calculator", "args": {"expression": "2 + 2"}, "id": "c1"}],
    )
    fake = _RecordingModel(
        messages=iter([tool_call_msg, AIMessage(content="The answer is four.")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    out = "".join([
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="2 + 2 ?", system_prompt="s",
            params=_PARAMS, thread_id="c-nonempty", tools=[calculator],
        )
    ])

    assert out == "The answer is four."
    # calculator("2 + 2") == "4"; if the fallback wrongly fired it would be
    # appended here. Its absence proves the fallback stayed dormant.
    assert "4" not in out


# ===================== Vision input (mlx-vlm swap, image content-parts) =====================

_IMG = {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANS"}}


async def test_astream_accepts_multimodal_user_message(monkeypatch):
    """A list user_message (text + image_url parts) reaches a vision model as a
    HumanMessage whose content keeps the image part (supports_vision=True is
    required since #212: anything else strips images)."""
    fake = _RecordingModel(messages=iter([AIMessage(content="a red square")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    async for _ in runner.astream_text(
        llm=_Llm(), user_message=[{"type": "text", "text": "what is this?"}, _IMG],
        system_prompt="sys", params=_PARAMS, thread_id="c-img", summarize=False,
        supports_vision=True,
    ):
        pass

    last = fake.received[-1][-1]
    assert last.type == "human"
    assert isinstance(last.content, list)
    assert any(p.get("type") == "image_url" for p in last.content)


async def test_kb_merge_preserves_image_parts(monkeypatch):
    """With a KB block AND an image, the merged last message carries the KB
    block in its text part and STILL keeps the image part."""
    fake = _RecordingModel(messages=iter([AIMessage(content="90 jours.")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    async for _ in runner.astream_text(
        llm=_Llm(), user_message=[{"type": "text", "text": "Quel préavis ?"}, _IMG],
        system_prompt="sys", params=_PARAMS, thread_id="c-kb-img",
        kb_context_block=_BLOCK_1, kb_language_line="Réponds en français.",
        supports_vision=True,
    ):
        pass

    merged = fake.received[-1][-1]
    assert isinstance(merged.content, list)
    text_part = next(p for p in merged.content if p.get("type") == "text")
    assert _BLOCK_1 in text_part["text"]
    assert "Quel préavis ?" in text_part["text"]
    assert any(p.get("type") == "image_url" for p in merged.content)


async def test_stale_images_stripped_on_followup(monkeypatch):
    """Turn 1 sends an image; turn 2 is text-only. Turn 2's model call must NOT
    re-send turn 1's image (it collapses to an [image] marker), keeping the
    small VLM context bounded — vision is single-turn."""
    fake = _RecordingModel(
        messages=iter([AIMessage(content="r1"), AIMessage(content="r2")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    # supports_vision=True so ONLY the stale-image middleware is exercised
    # (anything else would add _StripImagesForTextModel too since #212).
    async for _ in runner.astream_text(
        llm=_Llm(), user_message=[{"type": "text", "text": "see this"}, _IMG],
        system_prompt="s", params=_PARAMS, thread_id="c-strip", summarize=True,
        supports_vision=True,
    ):
        pass
    async for _ in runner.astream_text(
        llm=_Llm(), user_message="and now?", system_prompt="s",
        params=_PARAMS, thread_id="c-strip", summarize=True,
        supports_vision=True,
    ):
        pass

    second_call = fake.received[-1]
    # No image_url survives anywhere in turn 2's request.
    for m in second_call:
        if isinstance(m.content, list):
            assert all(p.get("type") != "image_url" for p in m.content)
    # Turn 1's human message kept its text + an [image] marker (flattened).
    past_human = [m for m in second_call if m.type == "human"][0]
    assert "[image]" in past_human.content
    assert "see this" in past_human.content


async def test_images_stripped_for_non_vision_model(monkeypatch):
    """A text-only model (supports_vision=False) must never receive image parts:
    the CURRENT turn's image is flattened to an [image] marker so inference is
    clean text instead of broken/garbage output (#133)."""
    fake = _RecordingModel(messages=iter([AIMessage(content="ok")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=None)

    async for _ in runner.astream_text(
        llm=_Llm(), user_message=[{"type": "text", "text": "what is this"}, _IMG],
        system_prompt="s", params=_PARAMS, supports_vision=False,
    ):
        pass

    sent = fake.received[-1]
    for m in sent:
        if isinstance(m.content, list):
            assert all(p.get("type") != "image_url" for p in m.content)
    human = [m for m in sent if m.type == "human"][0]
    assert isinstance(human.content, str)
    assert "[image]" in human.content
    assert "what is this" in human.content


async def test_images_kept_for_vision_model(monkeypatch):
    """A vision model (supports_vision=True) keeps the current image attached (#133)."""
    fake = _RecordingModel(messages=iter([AIMessage(content="ok")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=None)

    async for _ in runner.astream_text(
        llm=_Llm(), user_message=[{"type": "text", "text": "what is this"}, _IMG],
        system_prompt="s", params=_PARAMS, supports_vision=True,
    ):
        pass

    last = fake.received[-1][-1]
    assert isinstance(last.content, list)
    assert any(p.get("type") == "image_url" for p in last.content)


async def test_images_stripped_when_vision_capability_unknown(monkeypatch):
    """Unknown vision capability (supports_vision=None) strips images too (#212):
    only a positively-detected vision model receives image parts, so a
    maybe-text-only model never breaks on an attachment."""
    fake = _RecordingModel(messages=iter([AIMessage(content="ok")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=None)

    async for _ in runner.astream_text(
        llm=_Llm(), user_message=[{"type": "text", "text": "what is this"}, _IMG],
        system_prompt="s", params=_PARAMS, supports_vision=None,
    ):
        pass

    sent = fake.received[-1]
    for m in sent:
        if isinstance(m.content, list):
            assert all(p.get("type") != "image_url" for p in m.content)
    human = [m for m in sent if m.type == "human"][0]
    assert isinstance(human.content, str)
    assert "[image]" in human.content
    assert "what is this" in human.content


# ===================== Agentic KB tool (issue #84) =====================

from unittest.mock import MagicMock  # noqa: E402

from src.agents.tools import KbToolContext, search_knowledge_base  # noqa: E402
from src.utils.kb_utils import KbExcerpt  # noqa: E402


def test_kb_tool_exposes_only_query_to_the_model():
    # The runtime context (kb_id, token_budget) must be hidden from the model;
    # only `query` is part of the tool schema the model sees.
    assert "query" in search_knowledge_base.args
    assert "runtime" not in search_knowledge_base.args


async def test_kb_tool_round_trip_searches_with_runtime_context(monkeypatch):
    """The model calls search_knowledge_base(query=...); the tool retrieves with
    the HIDDEN kb_id/token_budget from its runtime context, and its grounded
    result reaches the second model call as a ToolMessage."""
    excerpts = [KbExcerpt(source_file="contrat.pdf", text="Le préavis est de 90 jours.")]
    mock_retrieve = MagicMock(return_value=excerpts)
    monkeypatch.setattr("src.agents.tools.retrieve_kb_excerpts", mock_retrieve)

    tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "search_knowledge_base",
            "args": {"query": "préavis de résiliation"},
            "id": "k1",
        }],
    )
    fake = _RecordingModel(messages=iter([tool_call, AIMessage(content="90 jours.")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="Quel est le préavis ?", system_prompt="sys",
            params=_PARAMS, thread_id="c-kbtool",
            tools=[search_knowledge_base],
            context=KbToolContext(kb_id=7, token_budget=1000),
        )
    ]

    assert "".join(out) == "90 jours."
    # query from the model + kb_id/budget from the hidden runtime context
    mock_retrieve.assert_called_once_with("préavis de résiliation", 7, 1000)
    tool_messages = [m for m in fake.received[-1] if m.type == "tool"]
    assert tool_messages
    assert "[Document: contrat.pdf]" in tool_messages[-1].text
    assert "90 jours" in tool_messages[-1].text


async def test_kb_tool_returns_not_found_message_on_empty_pool(monkeypatch):
    monkeypatch.setattr("src.agents.tools.retrieve_kb_excerpts", MagicMock(return_value=[]))
    tool_call = AIMessage(
        content="",
        tool_calls=[{"name": "search_knowledge_base", "args": {"query": "x"}, "id": "k2"}],
    )
    fake = _RecordingModel(
        messages=iter([tool_call, AIMessage(content="Ce n'est pas dans les documents.")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    async for _ in runner.astream_text(
        llm=_Llm(), user_message="?", system_prompt="s", params=_PARAMS, thread_id="c-empty",
        tools=[search_knowledge_base], context=KbToolContext(kb_id=7, token_budget=1000),
    ):
        pass

    tool_messages = [m for m in fake.received[-1] if m.type == "tool"]
    assert "not in their documents" in tool_messages[-1].text


def test_build_middleware_includes_kb_tool_strip():
    built = AgentRunner()._build_middleware(ToolableFakeChatModel(messages=iter([])))
    assert any(type(m).__name__ == "_StripStaleKbToolMessages" for m in built)


async def test_stale_kb_tool_results_placeholdered_on_followup(monkeypatch):
    """The checkpointer persists every KB ToolMessage; on a follow-up the model
    request must placeholder PAST turns' (bulky) excerpts to avoid multi-turn
    pollution, while keeping the CURRENT turn's result intact and the
    AIMessage(tool_calls) -> ToolMessage pairing valid."""
    ex1 = [KbExcerpt(source_file="d1.pdf", text="Le préavis est de 90 jours.")]
    ex2 = [KbExcerpt(source_file="d2.pdf", text="Le SLA est de 99,7 pourcent.")]
    monkeypatch.setattr(
        "src.agents.tools.retrieve_kb_excerpts", MagicMock(side_effect=[ex1, ex2])
    )

    tc1 = AIMessage(
        content="",
        tool_calls=[{"name": "search_knowledge_base", "args": {"query": "préavis"}, "id": "a"}],
    )
    tc2 = AIMessage(
        content="",
        tool_calls=[{"name": "search_knowledge_base", "args": {"query": "sla"}, "id": "b"}],
    )
    fake = _RecordingModel(
        messages=iter([tc1, AIMessage(content="r1"), tc2, AIMessage(content="r2")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())
    ctx = KbToolContext(kb_id=7, token_budget=1000)

    for q in ("q1", "q2"):
        async for _ in runner.astream_text(
            llm=_Llm(), user_message=q, system_prompt="s", params=_PARAMS,
            thread_id="c-kbstrip", summarize=True,
            tools=[search_knowledge_base], context=ctx,
        ):
            pass

    last_call = fake.received[-1]  # turn 2, post-tool model call
    tool_msgs = [m for m in last_call if m.type == "tool"]
    # Pairing preserved: both ToolMessages still present (none dropped).
    assert len(tool_msgs) == 2
    # Past turn's real excerpts are gone (placeholdered)…
    assert "90 jours" not in "".join(m.text for m in last_call)
    assert any("earlier turn omitted" in m.content for m in tool_msgs)
    # …and the current turn's KB result is intact.
    assert any("99,7" in m.text for m in tool_msgs)


# ===================== Structured event stream (issue #90) =====================


def _answers(events):
    return "".join(e["text"] for e in events if e["t"] == "answer")


def _thinking(events):
    return "".join(e["text"] for e in events if e["t"] == "thinking")


async def _events(runner, **kwargs):
    return [e async for e in runner.astream_text(emit_events=True, **kwargs)]


async def test_events_answer_only_stream(monkeypatch):
    """A plain answer surfaces as ``answer`` events only (no thinking/tool)."""
    fake = ToolableFakeChatModel(messages=iter([AIMessage(content="Python is awesome")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    events = await _events(
        runner, llm=_Llm(), user_message="hi", system_prompt="s",
        params=_PARAMS, thread_id="e1", summarize=False,
    )

    assert _answers(events) == "Python is awesome"
    assert all(e["t"] == "answer" for e in events)


async def test_events_split_thinking_from_answer(monkeypatch):
    """Inline ``<think>...</think>`` is routed to ``thinking`` events; the answer
    text stays clean (no tag leakage)."""
    fake = ToolableFakeChatModel(
        messages=iter([AIMessage(content="<think>reasoning here</think>Answer text")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    events = await _events(
        runner, llm=_Llm(), user_message="hi", system_prompt="s",
        params=_PARAMS, thread_id="e2", summarize=False,
    )

    assert _answers(events) == "Answer text"
    assert _thinking(events) == "reasoning here"
    assert "<think>" not in _answers(events) and "</think>" not in _answers(events)


async def test_str_mode_drops_thinking_keeps_answer(monkeypatch):
    """Default (str) mode -- used by arena -- yields ONLY answer text and strips
    inline thinking, preserving the plain-text wire."""
    fake = ToolableFakeChatModel(
        messages=iter([AIMessage(content="<think>reasoning here</think>Answer text")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    out = [
        t
        async for t in runner.astream_text(
            llm=_Llm(), user_message="hi", system_prompt="s",
            params=_PARAMS, thread_id="e3", summarize=False,
        )
    ]

    assert "".join(out) == "Answer text"
    assert all(isinstance(t, str) for t in out)


async def test_events_tool_call_then_result_then_answer(monkeypatch):
    """A full agentic loop yields, in order: one complete ``tool_call`` (args as a
    parsed dict, never raw fragments), one ``tool_result``, then ``answer``."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "calculator",
            "args": {"expression": "1240 + 1378 + 1456 + 1689"},
            "id": "call-1",
        }],
    )
    fake = _RecordingModel(
        messages=iter([tool_call_msg, AIMessage(content="Le total est 5763 k€.")])
    )
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    events = await _events(
        runner, llm=_Llm(), user_message="Additionne.", system_prompt="s",
        params=_PARAMS, thread_id="e4", tools=[calculator],
    )

    tool_calls = [e for e in events if e["t"] == "tool_call"]
    tool_results = [e for e in events if e["t"] == "tool_result"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "calculator"
    assert tool_calls[0]["args"] == {"expression": "1240 + 1378 + 1456 + 1689"}
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "calculator"
    assert tool_results[0]["text"] == "5763"
    assert _answers(events) == "Le total est 5763 k€."
    # Ordering: tool_call precedes its result, which precedes the final answer.
    kinds = [e["t"] for e in events]
    assert kinds.index("tool_call") < kinds.index("tool_result") < kinds.index("answer")


async def test_events_empty_final_fallback_arrives_as_answer(monkeypatch):
    """#90: the empty-final fallback (last tool result) is emitted as an
    ``answer`` event -- not a raw string, never an error."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "calculator",
            "args": {"expression": "1240 + 1378 + 1456"},
            "id": "call-1",
        }],
    )
    fake = _RecordingModel(messages=iter([tool_call_msg, AIMessage(content="")]))
    _patch_model(monkeypatch, fake)
    runner = AgentRunner(checkpointer=InMemorySaver())

    events = await _events(
        runner, llm=_Llm(), user_message="1240 + 1378 + 1456 ?", system_prompt="s",
        params=_PARAMS, thread_id="e5", tools=[calculator],
    )

    assert _answers(events).strip() == "4074"
    assert any(e["t"] == "tool_result" and e["text"] == "4074" for e in events)
    assert all(ERROR_SENTINEL not in e.get("text", "") for e in events)


async def test_events_construction_error_is_sentinel_answer(monkeypatch):
    """#252: a construction failure yields a single ``answer`` event carrying the
    curated sentinel (services later maps it to an ``error`` wire event)."""
    def _boom(llm, **kw):
        raise RuntimeError("model load failed: /secret/path")

    monkeypatch.setattr(runner_module, "build_chat_model", _boom)
    runner = AgentRunner(checkpointer=InMemorySaver())

    events = await _events(
        runner, llm=_Llm(), user_message="hi", system_prompt="s",
        params=_PARAMS, thread_id="e6",
    )

    assert len(events) == 1
    assert events[0]["t"] == "answer"
    assert ERROR_SENTINEL in events[0]["text"]
    assert "Traceback" not in events[0]["text"]
    assert "/secret/path" not in events[0]["text"]
