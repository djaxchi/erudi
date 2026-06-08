"""Picklable child-process entry point for `mlx_vlm.server`.

Why a dedicated module
----------------------
The MLX engine spawns the OpenAI-compatible `mlx_vlm.server` HTTP server in a
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

The two-function split (`_import_mlx_vlm_server_main` + `run_mlx_vlm_server`)
keeps the heavy `mlx_vlm.server` import lazy and — critically — patchable from
unit tests that run on Linux CI where `mlx-vlm` is not installed.

Contract
--------
`run_mlx_vlm_server(argv)` replaces `sys.argv` with the supplied list and calls
the real `mlx_vlm.server.cli.main()`. The first element of `argv` is the
conventional program name; the rest are the CLI flags that mlx-vlm's argparse
expects (`--model`, `--host`, `--port`, `--log-level`, ...). `main()` parses
them, exports the matching env vars (e.g. `MLX_VLM_PRELOAD_MODEL` from
`--model`), and launches `uvicorn.run("mlx_vlm.server:app", ...)`.

Once invoked, this function blocks for the lifetime of the HTTP server,
exiting only when the child process is terminated by the parent.
"""
from __future__ import annotations

from typing import List


def _import_mlx_vlm_server_main():
    """Import and return `mlx_vlm.server.cli.main`.

    Extracted as a separate function so tests can patch this seam without
    requiring `mlx-vlm` to be installed on the CI runner. The real import is
    deferred until first call, both for test isolation and to keep the
    parent-process import time low.
    """
    from mlx_vlm.server.cli import main as _main
    return _main


def run_mlx_vlm_server(argv: List[str]) -> None:
    """Child-process entry: set `sys.argv = argv` then run `mlx_vlm.server`'s main().

    Args:
        argv: Full argument vector. `argv[0]` is the program name
            (conventionally ``"mlx_vlm.server"``); the rest are CLI flags
            consumed by argparse inside `main()`.

    Returns:
        None. This call blocks for the lifetime of the HTTP server.
    """
    import sys

    sys.argv = list(argv)
    main = _import_mlx_vlm_server_main()
    main()
