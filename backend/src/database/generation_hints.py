"""Per-model sampling defaults (#388, closes the #136-A item).

Two halves, deliberately separated:

* **Capture** (network, build/CI time and post-download): read the *facts* a base
  repo ships about how it likes to be sampled -- a whitelisted subset of
  ``generation_config.json``, the context window from ``config.json`` and whether
  the chat template knows ``enable_thinking``. The facts are stored verbatim in
  ``llms.generation_hints`` (JSON, nullable). Never the resolved result: a change
  to the curated table below must apply to already-downloaded rows without a
  backfill.

* **Resolution** (pure, read time): ``resolve_sampling_defaults(llm)`` merges
  ``curated profile > guarded HF generation_config > fallback constants`` into
  the defaults a new conversation / arena panel starts from and the extra
  sampling keys the model factory sends. A row without hints resolves to
  exactly today's constants, so every request body validated by the #129 eval
  campaign stays byte-identical. ``top_k`` / ``min_p`` / ``presence_penalty``
  exist only when a layer defines them: they are never sent otherwise, so the
  llama-server implicit defaults (top_k 40 / min_p 0.05) that #129 validated on
  GGUF are untouched.

Repo rule: a sampling default changes only with an eval. The curated table is
the one layer that can carry an eval reference, which is why it has the highest
precedence -- and why it ships EMPTY until the maintainer runs the campaign.
"""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.core.logging import logger

# ---------------------------------------------------------------------------
# Fallback constants -- the ONE place today's defaults live (#129-validated).
# ---------------------------------------------------------------------------
FALLBACK_TEMPERATURE = 0.2
FALLBACK_TOP_P = 0.95
FALLBACK_MAX_TOKENS = 1024
# Tuned through the #129 eval campaign (see the run journal in the issue): the
# legacy 5-token window was blind to sentence-level cycles (small models looped
# whole list items to the token cap), while 1.2 over a wide window over-penalized
# token reuse and mangled proper nouns from the question. 1.1 over 64 tokens
# kills the loops and leaves precision intact.
FALLBACK_REPETITION_PENALTY = 1.1
FALLBACK_REPETITION_CONTEXT_SIZE = 64
# "No cap": mirrors the Conversation.max_tokens validator upper bound.
UNBOUNDED_CONTEXT_TOKENS = 32768

SOURCE_CURATED = "curated"
SOURCE_HF = "hf_generation_config"
SOURCE_FALLBACK = "fallback"

# Keys copied from generation_config.json. Everything else (token ids,
# transformers_version, ...) is noise for sampling.
GENERATION_CONFIG_KEYS: Tuple[str, ...] = (
    "temperature", "top_p", "top_k", "min_p", "repetition_penalty", "presence_penalty",
    "do_sample",
)
# Sampling keys that are user-facing / always on the wire.
_CORE_KEYS = ("temperature", "top_p", "repetition_penalty")
# Sampling keys sent ONLY when a layer defines them.
_OPTIONAL_KEYS = ("top_k", "min_p", "presence_penalty")


# ---------------------------------------------------------------------------
# Curated profiles (eval-referenced). Highest precedence.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CuratedProfile:
    """A hand-validated sampling profile.

    ``types`` matches ``Llm.type`` (empty = any family), ``slug_pattern`` is a
    case-insensitive regex tried on ``link`` then ``name``, ``supports_thinking``
    matches the captured flag (``None`` = don't care). ``values`` may carry any of
    temperature / top_p / top_k / min_p / repetition_penalty /
    repetition_context_size / presence_penalty. ``evidence`` is the eval run the
    entry rests on (issue + comment) and is mandatory.
    """

    types: Tuple[str, ...] = ()
    slug_pattern: Optional[str] = None
    supports_thinking: Optional[bool] = None
    values: Dict[str, Any] = field(default_factory=dict)
    evidence: str = ""

    def matches(self, llm: Any, hints: Dict[str, Any]) -> bool:
        if self.types and getattr(llm, "type", None) not in self.types:
            return False
        if self.supports_thinking is not None and hints.get("supports_thinking") is not self.supports_thinking:
            return False
        if self.slug_pattern:
            rx = re.compile(self.slug_pattern, re.IGNORECASE)
            haystacks = [str(getattr(llm, "link", "") or ""), str(getattr(llm, "name", "") or "")]
            if not any(rx.search(h) for h in haystacks):
                return False
        return True


# Empty on purpose: the design requires a #129-style eval before an entry that
# changes behaviour lands (the Qwen3 thinking profile is the first candidate;
# until then the HF layer already yields its shipped 0.6 / 0.95 / top_k 20).
SAMPLING_PROFILES: Tuple[CuratedProfile, ...] = ()


# ---------------------------------------------------------------------------
# Resolved shape
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SamplingDefaults:
    temperature: float
    top_p: float
    max_tokens: int
    repetition_penalty: float
    repetition_context_size: int
    max_tokens_cap: int
    source: str
    top_k: Optional[int] = None
    min_p: Optional[float] = None
    presence_penalty: Optional[float] = None
    base_repo: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def wire_kwargs(self) -> Dict[str, Any]:
        """Extra sampling params for the local server (HF vocabulary; engines
        translate). Optional keys are present ONLY when defined."""
        out: Dict[str, Any] = {
            "repetition_penalty": self.repetition_penalty,
            "repetition_context_size": self.repetition_context_size,
        }
        for key in _OPTIONAL_KEYS:
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        return out


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    f = float(value)
    return None if math.isnan(f) or math.isinf(f) else f


def _as_int(value: Any) -> Optional[int]:
    f = _as_float(value)
    return None if f is None else int(f)


def guarded_generation_config(block: Any) -> Optional[Dict[str, Any]]:
    """Sanitize a captured generation_config subset into usable sampling values.

    Rules (design #388 section 3.4):
    - ``do_sample: false`` -> the whole block is ignored (the vendor disables
      sampling; our sliders would contradict it).
    - ``top_k == 1`` or ``temperature < 0.05`` -> "vendor says greedy": keep
      exactly what ships (e.g. Qwen2.5-VL). No second-guessing.
    - temperature clamped to [0, 2]; top_p must be in (0, 1], top_k >= 0, min_p in
      [0, 1], presence_penalty in [-2, 2], repetition_penalty > 0 -- out-of-range
      or non-numeric keys are DROPPED (per-key fall-through), never coerced.
    """
    if not isinstance(block, dict):
        return None
    if block.get("do_sample") is False:
        return None
    out: Dict[str, Any] = {}
    temperature = _as_float(block.get("temperature"))
    if temperature is not None:
        out["temperature"] = min(2.0, max(0.0, temperature))
    top_p = _as_float(block.get("top_p"))
    if top_p is not None and 0.0 < top_p <= 1.0:
        out["top_p"] = top_p
    top_k = _as_int(block.get("top_k"))
    if top_k is not None and top_k >= 0:
        out["top_k"] = top_k
    min_p = _as_float(block.get("min_p"))
    if min_p is not None and 0.0 <= min_p <= 1.0:
        out["min_p"] = min_p
    presence = _as_float(block.get("presence_penalty"))
    if presence is not None and -2.0 <= presence <= 2.0:
        out["presence_penalty"] = presence
    rep = _as_float(block.get("repetition_penalty"))
    if rep is not None and rep > 0.0:
        out["repetition_penalty"] = rep
    return out or None


def _hints_of(llm: Any) -> Dict[str, Any]:
    hints = getattr(llm, "generation_hints", None)
    return hints if isinstance(hints, dict) else {}


def max_tokens_cap(context_length: Any, engine: Any = None) -> int:
    """``min(model context window, engine context window)``, both optional.

    The engine window is the llama.cpp ``-c`` (``ERUDI_CTX``, 4096 by default);
    MLX has none. Informational for the UI (the max-tokens field's ceiling, the
    #136 "2000" item) and a soft server-side clamp -- never a rejection.
    """
    if engine is None:
        from src.core import config
        engine = getattr(config, "LLM_Engine", None)
    engine_ctx = None
    probe = getattr(engine, "max_context_tokens", None) if engine is not None else None
    if callable(probe):
        try:
            engine_ctx = probe()
        except Exception:
            engine_ctx = None
    model_ctx = _as_int(context_length)
    cap = UNBOUNDED_CONTEXT_TOKENS
    if model_ctx is not None and model_ctx > 0:
        cap = min(cap, model_ctx)
    if isinstance(engine_ctx, int) and engine_ctx > 0:
        cap = min(cap, engine_ctx)
    return max(1, cap)


def resolve_sampling_defaults(llm: Any, *, engine: Any = None) -> SamplingDefaults:
    """Pure resolver: ``curated > guarded HF generation_config > fallback``.

    Reads ``generation_hints`` / ``type`` / ``link`` / ``name`` off ``llm`` (ORM
    row, Pydantic model or any duck) and never touches the network or the DB.
    """
    hints = _hints_of(llm)
    values: Dict[str, Any] = {
        "temperature": FALLBACK_TEMPERATURE,
        "top_p": FALLBACK_TOP_P,
        "max_tokens": FALLBACK_MAX_TOKENS,
        "repetition_penalty": FALLBACK_REPETITION_PENALTY,
        "repetition_context_size": FALLBACK_REPETITION_CONTEXT_SIZE,
    }
    optional: Dict[str, Any] = {}
    source = SOURCE_FALLBACK

    hf = guarded_generation_config(hints.get("generation_config"))
    if hf:
        source = SOURCE_HF
        _merge_layer(values, optional, hf)

    for profile in SAMPLING_PROFILES:
        if profile.matches(llm, hints):
            source = SOURCE_CURATED
            _merge_layer(values, optional, profile.values, allow_context_size=True)
            break

    cap = max_tokens_cap(hints.get("context_length"), engine)
    values["max_tokens"] = min(int(values["max_tokens"]), cap)
    return SamplingDefaults(
        temperature=values["temperature"],
        top_p=values["top_p"],
        max_tokens=values["max_tokens"],
        repetition_penalty=values["repetition_penalty"],
        repetition_context_size=values["repetition_context_size"],
        max_tokens_cap=cap,
        source=source,
        top_k=optional.get("top_k"),
        min_p=optional.get("min_p"),
        presence_penalty=optional.get("presence_penalty"),
        base_repo=hints.get("base_repo") if isinstance(hints.get("base_repo"), str) else None,
    )


def _merge_layer(values: Dict[str, Any], optional: Dict[str, Any], layer: Dict[str, Any],
                 *, allow_context_size: bool = False) -> None:
    for key in _CORE_KEYS:
        if key in layer:
            values[key] = layer[key]
    if allow_context_size and "repetition_context_size" in layer:
        values["repetition_context_size"] = layer["repetition_context_size"]
    for key in _OPTIONAL_KEYS:
        if key in layer:
            optional[key] = layer[key]


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
_GENERATION_CONFIG_FILE = "generation_config.json"
_CONFIG_FILE = "config.json"
_TOKENIZER_CONFIG_FILE = "tokenizer_config.json"
_CHAT_TEMPLATE_FILE = "chat_template.jinja"

# Memoized per base repo for the life of the process: the ~640 derived catalog
# rows collapse onto ~300 unique bases, and failures are remembered too so a
# gated family is not re-probed for every quant of it.
_CAPTURE_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}


def reset_capture_cache() -> None:
    _CAPTURE_CACHE.clear()


def _chat_template_text(chat_template: Any) -> Optional[str]:
    """``chat_template`` may be a string or a list of ``{name, template}``."""
    if isinstance(chat_template, str):
        return chat_template
    if isinstance(chat_template, list):
        parts = [t.get("template", "") for t in chat_template if isinstance(t, dict)]
        return "\n".join(p for p in parts if isinstance(p, str))
    return None


def _context_length_of(config: Optional[Dict[str, Any]]) -> Optional[int]:
    if not isinstance(config, dict):
        return None
    candidates: List[Any] = [config.get("max_position_embeddings")]
    text_config = config.get("text_config")
    if isinstance(text_config, dict):
        candidates.append(text_config.get("max_position_embeddings"))
    for value in candidates:
        n = _as_int(value)
        if n is not None and n > 0:
            return n
    return None


def build_generation_hints(
    *,
    base_repo: Optional[str],
    generation_config: Optional[Dict[str, Any]],
    config: Optional[Dict[str, Any]],
    chat_template: Any,
    captured_at: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Assemble the stored facts from the three (optional) source documents.

    Returns ``None`` when nothing at all was captured, so the column stays NULL
    ("no hints") rather than holding an empty envelope.
    """
    template_text = _chat_template_text(chat_template)
    if generation_config is None and config is None and template_text is None:
        return None
    hints: Dict[str, Any] = {"base_repo": base_repo}
    if isinstance(generation_config, dict):
        hints["generation_config"] = {
            k: generation_config[k] for k in GENERATION_CONFIG_KEYS if k in generation_config
        }
    hints["supports_thinking"] = (
        ("enable_thinking" in template_text) if template_text is not None else None
    )
    hints["context_length"] = _context_length_of(config)
    hints["captured_at"] = captured_at or date.today().isoformat()
    return hints


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _hints_from_readers(base_repo: Optional[str], read_json, read_text) -> Optional[Dict[str, Any]]:
    """Shared assembly for the network and local paths. ``read_json(name)`` /
    ``read_text(name)`` return ``None`` for a missing file and raise on a broken
    one (the caller decides whether that aborts the capture)."""
    generation_config = read_json(_GENERATION_CONFIG_FILE)
    config = read_json(_CONFIG_FILE)
    tokenizer_config = read_json(_TOKENIZER_CONFIG_FILE)
    chat_template: Any = None
    if tokenizer_config is not None:
        chat_template = tokenizer_config.get("chat_template")
    if _chat_template_text(chat_template) is None:
        # transformers >= 4.5x moves the template to a standalone jinja file.
        chat_template = read_text(_CHAT_TEMPLATE_FILE)
    return build_generation_hints(
        base_repo=base_repo, generation_config=generation_config, config=config,
        chat_template=chat_template,
    )


def _capture_uncached(base_repo: str, hf_api: Any) -> Optional[Dict[str, Any]]:
    from huggingface_hub.errors import EntryNotFoundError

    def fetch(filename: str) -> Optional[Path]:
        try:
            return Path(hf_api.hf_hub_download(repo_id=base_repo, filename=filename))
        except EntryNotFoundError:
            return None
        # GatedRepoError / RepositoryNotFoundError / HTTP errors propagate: the
        # repo as a whole is unreadable, no point probing the other files.

    def read_json(filename: str) -> Optional[Dict[str, Any]]:
        path = fetch(filename)
        return _load_json(path) if path is not None else None

    def read_text(filename: str) -> Optional[str]:
        path = fetch(filename)
        return path.read_text(encoding="utf-8") if path is not None else None

    return _hints_from_readers(base_repo, read_json, read_text)


def capture_generation_hints(base_repo: Optional[str], hf_api: Any) -> Optional[Dict[str, Any]]:
    """Read a base repo's sampling facts from HuggingFace. Best-effort: ``None``
    on any failure (gated repo, network, malformed file), never raises.

    ``hf_api`` is the retrying client from ``src.core.config.get_hf_api`` (its
    ``hf_hub_download`` paces and retries 429s like the other catalog calls).
    """
    if not base_repo or hf_api is None:
        return None
    if base_repo in _CAPTURE_CACHE:
        return copy.deepcopy(_CAPTURE_CACHE[base_repo])
    try:
        hints = _capture_uncached(base_repo, hf_api)
    except Exception as e:
        logger.warning(f"Generation hints capture failed for {base_repo}: {e}")
        hints = None
    _CAPTURE_CACHE[base_repo] = hints
    return copy.deepcopy(hints)


def read_local_generation_hints(model_dir: Path, base_repo: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Offline variant for a downloaded MLX directory (which ships the same three
    files). GGUF artifacts carry none of them -> ``None``. Never raises."""
    model_dir = Path(model_dir)
    if not model_dir.is_dir():
        return None

    def read_json(filename: str) -> Optional[Dict[str, Any]]:
        path = model_dir / filename
        return _load_json(path) if path.is_file() else None

    def read_text(filename: str) -> Optional[str]:
        path = model_dir / filename
        return path.read_text(encoding="utf-8") if path.is_file() else None

    try:
        return _hints_from_readers(base_repo, read_json, read_text)
    except Exception as e:
        logger.warning(f"Local generation hints unreadable in {model_dir}: {e}")
        return None


def resolve_base_repo(repo_id: str, tags: Optional[Iterable[str]]) -> str:
    """The repo whose generation facts apply to ``repo_id``: the first
    ``base_model:<relation>:<target>`` card tag (a quant/finetune inherits its
    base's sampling), else the repo itself."""
    from src.database.catalog_classify import _REL_RE

    for tag in tags or []:
        m = _REL_RE.match(str(tag))
        if m:
            return m.group(2)
    return repo_id
