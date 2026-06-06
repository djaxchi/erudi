"""Smoke test: the LangChain agent stack is installed and the exact API
surface the refactor depends on is importable.

Fast guard so a missing/renamed dependency fails loudly in CI
(``pytest --ignore=tests/e2e -m "not mlx_only"``) rather than at runtime in
the middle of a stream. Every symbol asserted here is used by the new
``src.agents`` package or the checkpointer wiring.
"""

import pytest

pytestmark = pytest.mark.unit


def test_core_agent_imports():
    from langchain.agents import create_agent, AgentState  # noqa: F401
    from langchain_openai import ChatOpenAI  # noqa: F401


def test_checkpointer_imports():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.memory import InMemorySaver  # noqa: F401

    # B3: deleting a conversation must purge its checkpointer thread.
    assert hasattr(AsyncPostgresSaver, "adelete_thread")
    # Held-open lifespan construction relies on from_conn_string.
    assert hasattr(AsyncPostgresSaver, "from_conn_string")


def test_middleware_imports():
    from langchain.agents.middleware import (  # noqa: F401
        SummarizationMiddleware,
        AgentMiddleware,
        ModelRequest,
        dynamic_prompt,
        before_model,
        wrap_model_call,
    )


def test_message_and_token_imports():
    from langchain_core.messages import (  # noqa: F401
        HumanMessage,
        AIMessage,
        SystemMessage,
        ToolMessage,
        AIMessageChunk,
        trim_messages,
        messages_to_dict,
        messages_from_dict,
    )

    # count_tokens_approximately lives under .utils in langchain-core 1.4,
    # NOT under langchain_core.messages directly.
    from langchain_core.messages.utils import count_tokens_approximately  # noqa: F401


def test_fake_chat_model_available_for_tests():
    # M4: agent tests inject a real BaseChatModel (GenericFakeChatModel),
    # never a bare AsyncMock — create_agent validates the model type and
    # runs it through the LangGraph runtime.
    from langchain_core.language_models.fake_chat_models import (  # noqa: F401
        GenericFakeChatModel,
    )
