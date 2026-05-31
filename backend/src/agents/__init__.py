"""LangChain/LangGraph agent layer for Erudi.

A thin transverse layer (consumed by ``domains/conversations`` and
``domains/arena`` services) that wraps the engine behind LangChain primitives:

  - ``model_factory`` — build a ``ChatOpenAI`` pointed at the local engine server
    and the engine-level serialization/idle-marker guard.
  - ``runner`` — ``AgentRunner``: one ``create_agent`` per turn, streamed as raw
    token text for the existing ``StreamingResponse(text/plain)`` contract.
  - ``prompts`` — size-adaptive system prompt construction.
  - ``checkpoint`` — SQLite checkpointer wiring (separate ``erudi-checkpoints.db``).
"""
