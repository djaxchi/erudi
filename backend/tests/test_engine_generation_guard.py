"""P2 — engine generation guard (resolves review BLOCKER B1 + MAJOR M1).

``generate_stream`` used to carry the active-marker invariant (``_last_used =
None`` suppresses the idle-cleanup monitor for the duration of a stream). The
LangChain path streams through ``ChatOpenAI`` directly, so the invariant is
re-homed in an engine-level ``generation_guard`` that the agent layer wraps
around model resolution + the whole stream. The guard also serializes
generations so concurrent different-model requests can't thrash the single-model
engine subprocess.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from src.engines.base_engine import BaseEngine

pytestmark = pytest.mark.unit


class _GuardEngine(BaseEngine):
    """Minimal subclass to exercise BaseEngine classmethods in isolation
    (abstract methods stay unimplemented — we never instantiate)."""


def _reset():
    _GuardEngine._model = None
    _GuardEngine._tokenizer = None
    _GuardEngine._last_used = None


async def test_guard_blocks_idle_cleanup_mid_stream():
    # Simulate a model that has been idle long enough to be reaped.
    _GuardEngine._model = object()
    _GuardEngine._last_used = datetime.now() - timedelta(seconds=10_000)
    try:
        assert _GuardEngine._should_cleanup() is True  # would be reaped right now
        async with _GuardEngine.generation_guard():
            # B1: marker None -> idle monitor must NOT tear down the model.
            assert _GuardEngine._last_used is None
            assert _GuardEngine._should_cleanup() is False
        # restored to a fresh timestamp on exit -> no longer idle.
        assert _GuardEngine._last_used is not None
        assert _GuardEngine._should_cleanup() is False
    finally:
        _reset()


async def test_guard_restores_marker_on_exception():
    _GuardEngine._model = object()
    _GuardEngine._last_used = datetime.now()
    try:
        with pytest.raises(ValueError):
            async with _GuardEngine.generation_guard():
                assert _GuardEngine._last_used is None
                raise ValueError("boom")
        # marker restored despite the error (so the model isn't pinned forever).
        assert _GuardEngine._last_used is not None
    finally:
        _reset()


async def test_guard_serializes_concurrent_generations():
    order: list[str] = []

    async def worker(name: str):
        async with _GuardEngine.generation_guard():
            order.append(f"{name}-enter")
            await asyncio.sleep(0.02)
            order.append(f"{name}-exit")

    try:
        await asyncio.gather(worker("A"), worker("B"))
        # M1: one generation fully completes before the other enters
        # (single-model engine — model swaps must not interleave).
        assert order in (
            ["A-enter", "A-exit", "B-enter", "B-exit"],
            ["B-enter", "B-exit", "A-enter", "A-exit"],
        )
    finally:
        _reset()
