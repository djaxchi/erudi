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


def _patch_text_only_tied_embeddings() -> bool:
    """Teach mlx-vlm to load MLX-format text-only checkpoints with tied embeddings.

    ``mlx_vlm.utils.load_model`` skips weight sanitization for MLX-format
    checkpoints (``format == "mlx"``), but tied-embedding architectures such as
    Gemma3 text-only (``gemma-3-270m``, ``gemma-3-1b``) ship *without* an
    ``lm_head.weight`` tensor: the inner ``mlx_lm`` model's ``sanitize()`` is
    what pops the untied ``lm_head`` so the strict weight load succeeds. With the
    sanitize step skipped, loading dies with
    ``ValueError: Missing 1 parameters: lm_head.weight``.

    We re-introduce that sanitize step at the text-only wrapper's
    ``load_weights`` boundary, *only* when ``lm_head.weight`` is genuinely
    absent, leaving every other (untied / multimodal / non-MLX) path untouched.

    Returns:
        True if the patch was applied (or already present), False if mlx-vlm's
        text-only module could not be imported (non-MLX hosts, CI). Idempotent.
    """
    try:
        from mlx_vlm.models import text_only
    except Exception:
        return False

    model_cls = getattr(text_only, "Model", None)
    if model_cls is None:
        return False
    if getattr(model_cls, "_erudi_tied_embed_patch", False):
        return True

    _orig_load_weights = model_cls.load_weights

    def _load_weights(self, weights, *args, **kwargs):
        items = list(weights.items()) if isinstance(weights, dict) else list(weights)
        has_lm_head = any(str(k).endswith("lm_head.weight") for k, _ in items)
        inner = getattr(getattr(self, "language_model", None), "_model", None)
        if not has_lm_head and inner is not None and hasattr(inner, "sanitize"):
            sanitized = inner.sanitize(dict(items))
            return inner.load_weights(list(sanitized.items()), *args, **kwargs)
        return _orig_load_weights(self, weights, *args, **kwargs)

    model_cls.load_weights = _load_weights
    model_cls._erudi_tied_embed_patch = True
    return True


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
    # Applied in-child before the server loads any model so MLX-format
    # tied-embedding text-only checkpoints (Gemma3 270m/1b) load cleanly.
    _patch_text_only_tied_embeddings()
    main = _import_mlx_vlm_server_main()
    main()
