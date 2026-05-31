"""Shared helpers for the test suite.

Currently exposes platform detection helpers used by both `conftest.py`
fixtures and per-file `pytest.mark.skipif` guards. Mirrors the dispatch
logic of `src.engines.base_engine.BaseEngine.get_engine()` without
re-evaluating it on every call site.

Imported explicitly by test files (not auto-discovered by pytest).
"""
from __future__ import annotations


def is_mlx_platform() -> bool:
    """Return True iff `BaseEngine.get_engine()` resolves to `MLX_Engine`."""
    try:
        from src.engines.base_engine import BaseEngine
        return BaseEngine.get_engine().__name__ == "MLX_Engine"
    except Exception:
        return False


def is_cuda_platform() -> bool:
    """Return True iff `BaseEngine.get_engine()` resolves to `CUDA_Engine`."""
    try:
        from src.engines.base_engine import BaseEngine
        return BaseEngine.get_engine().__name__ == "CUDA_Engine"
    except Exception:
        return False


def is_cpu_platform() -> bool:
    """Return True iff `BaseEngine.get_engine()` resolves to `CPU_Engine`."""
    try:
        from src.engines.base_engine import BaseEngine
        return BaseEngine.get_engine().__name__ == "CPU_Engine"
    except Exception:
        return False
