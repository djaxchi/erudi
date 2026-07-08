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


def _patch_gemma_end_of_turn_stop() -> bool:
    """Register Gemma's ``<end_of_turn>`` as a stop token in the mlx_vlm server (#249).

    mlx_vlm builds its stop-token set solely from ``config.eos_token_id`` (see
    ``ResponseGenerator._initialize_model``). Gemma checkpoints declare
    ``eos_token`` = ``<eos>`` (id 1), but their chat template ends *every turn*
    with ``<end_of_turn>`` (id 106) — which is therefore NOT in the stop set.
    Sampling runs past the answer and streams the literal ``<end_of_turn>`` token
    text plus multilingual garbage to the user. (The OpenAI ``stop`` request field
    does not help: mlx_vlm's generation loop halts on token *ids* in
    ``stop_tokens``, not on decoded strings.)

    We wrap ``_initialize_model`` to add the tokenizer's ``<end_of_turn>`` id to
    ``stop_tokens`` after the model loads — derived from the tokenizer, no
    hardcoded id. A no-op for tokenizers that don't define the token (the id then
    resolves to ``unk``), so non-Gemma checkpoints are untouched. Idempotent.

    Returns:
        True if the patch was applied (or already present), False if mlx-vlm's
        server generation module could not be imported (non-MLX hosts, CI).
    """
    try:
        from mlx_vlm.server import generation as _gen
    except Exception:
        return False

    rg = getattr(_gen, "ResponseGenerator", None)
    if rg is None or not hasattr(rg, "_initialize_model"):
        return False
    if getattr(rg, "_erudi_end_of_turn_patch", False):
        return True

    _orig_initialize_model = rg._initialize_model

    def _initialize_model(self):
        _orig_initialize_model(self)
        try:
            tok = getattr(self, "tokenizer", None)
            stop = getattr(self, "stop_tokens", None)
            if tok is None or stop is None:
                return
            unk = getattr(tok, "unk_token_id", None)
            tid = tok.convert_tokens_to_ids("<end_of_turn>")
            if tid is not None and tid >= 0 and tid != unk:
                stop.add(tid)
        except Exception:
            # Stop-token augmentation must never break model load.
            pass

    rg._initialize_model = _initialize_model
    rg._erudi_end_of_turn_patch = True
    return True


# Unmatchable thinking markers injected by `_patch_inline_thinking`. Model text
# can never contain a NUL byte, so these never match a marker (no split) and
# never partially match a chunk suffix (no `_split_partial` holdback latency).
_NEVER_OPEN_MARKER = "\x00erudi:no-thinking-split\x00"
_NEVER_CLOSE_MARKER = "\x00/erudi:no-thinking-split\x00"


def _patch_inline_thinking() -> bool:
    """Keep model reasoning INLINE in ``delta.content`` (#90).

    mlx-vlm 0.6.2 splits streamed thinking into a dedicated
    ``delta.reasoning`` field via ``ThinkingStreamState`` — a channel that
    ChatOpenAI silently drops, so the reasoning never reaches the runner. The
    design (#90) wants the raw ``<think>...</think>`` INLINE in
    ``delta.content`` so the runner's single streaming ThinkSplitter handles
    MLX exactly like llama-server with ``--reasoning-format none``.

    Why a monkeypatch and not configuration — on the pinned 0.6.2:

      - The server CLI does not accept ``--thinking-start-token`` (strict
        argparse: the child would die at boot), and the
        ``MLX_VLM_THINKING_START_TOKEN`` env var only exists in 0.6.4.
      - Even injected per-request, a sentinel start token cannot disable the
        split: ``_build_open_close_markers`` always APPENDS the built-in
        marker families (``<think>``, ``<|channel>thought``,
        ``<|START_THINKING|>``) after any custom pair.
      - ``ThinkingStreamState.__init__`` sets ``in_thinking =
        bool(enable_thinking)``, so with thinking enabled the stream starts in
        reasoning mode regardless of any marker. This is also why the class
        MUST be neutralized before passing ``--enable-thinking``: a
        non-thinking model (which never emits ``</think>``) would otherwise
        have its ENTIRE output routed to ``delta.reasoning`` — empty answers.

    So the single choke point is the class itself: force every instance to
    start OUTSIDE thinking with unmatchable markers. ``feed()`` then falls
    through to its plain-content branch, preserving upstream
    ``<|START_TEXT|>`` content-marker stripping and the downstream tool-call
    suppression untouched. The class object is mutated in place (never
    rebound), so it is irrelevant whether callers imported it before or after
    the patch.

    Returns:
        True if the patch was applied (or already present), False if
        mlx-vlm's server module could not be imported (non-MLX hosts, CI).
        Idempotent.
    """
    try:
        from mlx_vlm.server import responses_state
    except Exception:
        return False

    state_cls = getattr(responses_state, "ThinkingStreamState", None)
    if state_cls is None:
        return False
    if getattr(state_cls, "_erudi_inline_thinking_patch", False):
        return True

    _orig_init = state_cls.__init__

    def _init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        self.in_thinking = False
        self.open_close_markers = ((_NEVER_OPEN_MARKER, _NEVER_CLOSE_MARKER),)
        self.open_markers = (_NEVER_OPEN_MARKER,)
        self.close_markers = (_NEVER_CLOSE_MARKER,)

    state_cls.__init__ = _init
    state_cls._erudi_inline_thinking_patch = True
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
    # Register Gemma's <end_of_turn> as a stop token so generation halts at the
    # end of the answer instead of streaming the literal token + garbage (#249).
    _patch_gemma_end_of_turn_stop()
    # Applied in-child before the server starts so every ThinkingStreamState it
    # builds keeps reasoning inline in delta.content (#90) — see the patch's
    # docstring for why 0.6.2 offers no configuration path for this.
    _patch_inline_thinking()
    main = _import_mlx_vlm_server_main()
    main()
