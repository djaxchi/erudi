"""Launcher support utilities.

The launcher package exposes helpers shared between the cross-platform
startup script (`backend/run.py`) and the rest of the backend stack. It
keeps runtime-specific state (like data and log directories) in one place
so both the launcher and the FastAPI application resolve paths
consistently.
"""

from .runtime_paths import (
    RuntimePaths,
    ensure_runtime_paths_initialized,
    get_runtime_paths,
    initialize_runtime_paths,
)

__all__ = [
    "RuntimePaths",
    "ensure_runtime_paths_initialized",
    "get_runtime_paths",
    "initialize_runtime_paths",
]
