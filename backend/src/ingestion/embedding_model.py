"""On-demand availability + download of the KB embedding model (#146).

The Knowledge Base needs ``intfloat/multilingual-e5-small`` for BOTH embeddings
(``E5Embeddings``) and token-accurate chunking (``chunking._get_tokenizer``).
Both load it from ``config.CACHE_DIR`` (``data/models_cache``), so a single
download serves both consumers.

This module gates that download behind an explicit user action instead of the
implicit lazy Hugging Face fallback, so a fresh/offline install no longer fails
its first Knowledge Base use silently.

Design invariants:
- **Presence is filesystem-driven, never a DB flag.** ``embedding_model_available``
  checks the *weights* symlink in ``CACHE_DIR`` — huggingface_hub only links a
  file into ``snapshots/`` once it is fully downloaded, so a partial/interrupted
  download reads as unavailable and the gate re-appears. This also makes the
  state self-heal across backend restarts (in-memory flags are lost, the file
  check is not).
- **Download == the real load path** (``SentenceTransformer(..., cache_folder=CACHE_DIR)``),
  not a parallel ``snapshot_download`` — so the download target is ISO with where
  the app loads from, by construction, and it warms the resident singleton.
- **The download runs in a background thread**, decoupled from the HTTP request,
  so leaving the KB page never loses it; the UI polls a boolean status.
"""

from __future__ import annotations

import threading
from typing import Optional

from huggingface_hub import try_to_load_from_cache

from src.core import config
from src.core.logging import logger

EMBEDDING_MODEL_ID = "intfloat/multilingual-e5-small"
# The big weights file: its presence in the HF cache means a COMPLETE download
# (huggingface_hub links it into snapshots/ only once fully fetched). Checking a
# small file like config.json would false-positive on a partial download.
_WEIGHTS_FILENAME = "model.safetensors"

_lock = threading.Lock()
_state = {"downloading": False, "error": None}


def embedding_model_available() -> bool:
    """True iff the model weights are fully present in ``CACHE_DIR`` (no network)."""
    cached = try_to_load_from_cache(
        EMBEDDING_MODEL_ID, _WEIGHTS_FILENAME, cache_dir=str(config.CACHE_DIR)
    )
    return isinstance(cached, str)


def download_state() -> dict:
    """The gate's view: on-disk presence + transient background-task flags."""
    return {
        "available": embedding_model_available(),
        "downloading": _state["downloading"],
        "error": _state["error"],
    }


def _load_model():
    """The real load path — downloads into ``CACHE_DIR`` if absent (ISO with runtime)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_ID, cache_folder=str(config.CACHE_DIR))


def _spawn(target) -> None:
    threading.Thread(target=target, name="e5-download", daemon=True).start()


def _run_download() -> None:
    try:
        logger.info(f"Downloading embedding model {EMBEDDING_MODEL_ID} -> {config.CACHE_DIR}")
        _load_model()
        _state["error"] = None
    except Exception as exc:  # noqa: BLE001 - any failure is surfaced to the UI
        logger.error(f"Embedding model download failed: {exc}")
        _state["error"] = str(exc)
    finally:
        _state["downloading"] = False


def start_download() -> dict:
    """Idempotently kick off a background download. Returns the current state.

    No-op (returns current state) if the model is already present or a download
    is already running — guards double-clicks and concurrent callers.
    """
    with _lock:
        if not _state["downloading"] and not embedding_model_available():
            _state["downloading"] = True
            _state["error"] = None
            _spawn(_run_download)
    return download_state()


def _reset_state_for_tests(downloading: bool = False, error: Optional[str] = None) -> None:
    _state["downloading"] = downloading
    _state["error"] = error
