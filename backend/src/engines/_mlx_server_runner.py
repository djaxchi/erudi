"""Picklable child-process entry point for `mlx_lm.server`.

Why a dedicated module
----------------------
The MLX engine spawns the OpenAI-compatible `mlx_lm.server` HTTP server in a
separate process via `multiprocessing.Process(target=..., args=([argv],))`.
The `target` argument MUST be a top-level, importable, picklable function:

  - A lambda or a bound classmethod cannot be pickled by the `spawn` start
    method.
  - `spawn` is the only start method that works inside a PyInstaller frozen
    binary (where `sys.executable` is the launcher itself, not a Python
    interpreter). On the parent side, `mp.freeze_support()` and
    `set_start_method("spawn", force=True)` are configured in
    `backend/run.py` and `backend/tests/conftest.py`; the child reconstitutes
    the import graph and calls this function.

The two-function split (`_import_mlx_server_main` + `run_mlx_server`) keeps
the heavy `mlx_lm.server` import lazy and — critically — patchable from
unit tests that run on Linux CI where `mlx_lm` is not installed.

Contract
--------
`run_mlx_server(argv)` replaces `sys.argv` with the supplied list and calls
the real `mlx_lm.server.main()`. The first element of `argv` is the
conventional program name; the rest are the CLI flags that
`mlx_lm.server`'s argparse expects (`--model`, `--host`, `--port`, ...).

Once invoked, this function blocks for the lifetime of the HTTP server,
exiting only when the child process is terminated by the parent.
"""
from __future__ import annotations

from typing import List


def _import_mlx_server_main():
    """Import and return `mlx_lm.server.main`.

    Extracted as a separate function so tests can patch this seam without
    requiring `mlx_lm` to be installed on the CI runner. The real import is
    deferred until first call, both for test isolation and to keep the
    parent-process import time low.
    """
    from mlx_lm.server import main as _main
    return _main


def run_mlx_server(argv: List[str]) -> None:
    """Child-process entry: set `sys.argv = argv` then run `mlx_lm.server.main()`.

    Args:
        argv: Full argument vector. `argv[0]` is the program name
            (conventionally ``"mlx_lm.server"``); the rest are CLI flags
            consumed by argparse inside `main()`.

    Returns:
        None. This call blocks for the lifetime of the HTTP server.
    """
    import sys

    sys.argv = list(argv)
    main = _import_mlx_server_main()
    main()
