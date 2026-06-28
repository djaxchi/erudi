"""Pure, framework-free classification helpers for the HF catalog (#122).

No I/O, no SQLAlchemy, no huggingface_hub — every function takes plain data
(strings, lists, ints) so it is trivially unit-testable in isolation. ``seed.py``
wires these to live ``ModelInfo`` fields during discovery.

Why this exists: the old discovery marked any top ``text-generation`` repo from a
foundation org as ``is_base`` and parsed param size from the slug with a 7.0
fallback. That surfaced intermediate artifacts (``-assistant`` distillates,
``-qat-unquantized``), quant-of-quant derivatives, and mislabeled sizes as base
foundation models (#122). These helpers add the missing signals:

  - ``base_model:`` relation tags → authoritative derivative detection
  - ``pipeline_tag`` + name → capability CATEGORY (general/code/reasoning/…)
  - ``safetensors.total`` (with a slug sanity-check) → real parameter count
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# ============ Capability categories ============
# Stable string keys persisted on Llm.category and grouped by the frontend.
CAT_GENERAL = "general"
CAT_CODE = "code"
CAT_REASONING = "reasoning"
CAT_MATH = "math"
CAT_VISION = "vision"
CAT_MEDICAL = "medical"
CAT_FUNCTION = "function"
CAT_SAFETY = "safety"

ALL_CATEGORIES = (
    CAT_GENERAL, CAT_CODE, CAT_REASONING, CAT_MATH,
    CAT_VISION, CAT_MEDICAL, CAT_FUNCTION, CAT_SAFETY,
)

# Multimodal pipeline tags whose primary input/output is not plain text.
VISION_PIPELINES = frozenset({"image-text-to-text", "any-to-any", "visual-question-answering"})

# Slug tokens marking a raw (non-chat) pretrain. Kept deliberately small: only
# unambiguous pretrain markers, NOT instruct markers (it/instruct/chat) and NOT
# size/format tokens.
PRETRAIN_MARKERS = frozenset({"base", "pt", "pretrain", "pretrained"})

_REL_RE = re.compile(r"^base_model:(quantized|finetune|merge|adapter):(.+)$")


def relation_targets(tags: Optional[List[str]]) -> Dict[str, List[str]]:
    """Parse ``base_model:<relation>:<target>`` card tags into ``{relation: [targets]}``.

    HuggingFace stamps these on a repo's card to declare its lineage, e.g.
    ``base_model:quantized:google/gemma-3-4b-it`` on an MLX requant. ``relation``
    is one of quantized / finetune / merge / adapter.
    """
    out: Dict[str, List[str]] = {}
    for tag in tags or []:
        m = _REL_RE.match(tag)
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


def is_derivative(tags: Optional[List[str]]) -> bool:
    """True if the card declares this repo a quant / merge / adapter of something.

    Such repos are NOT foundation/base models — they are produced FROM another
    model. (``finetune`` is intentionally excluded: an instruct release is itself a
    finetune of its pretrain, so it would wrongly disqualify real base chat models.)
    """
    rel = relation_targets(tags)
    return any(k in rel for k in ("quantized", "merge", "adapter"))


def is_instruct(name: str) -> bool:
    """Whether a model slug looks like a usable chat model (vs a raw pretrain).

    Conservative: only an explicit pretrain marker token (``-base``/``-pt``)
    disqualifies. Modern chat models that drop the ``-instruct`` suffix
    (DeepSeek-V3, GLM-4.5, gpt-oss-20b) stay in; raw pretrain siblings are pruned
    separately by the caller via family dedup (keep ``…-it`` over ``…`` bare).
    """
    toks = re.split(r"[-_.]", name.lower())
    return not any(tok in PRETRAIN_MARKERS for tok in toks)


def _has_word(name_low: str, *words: str) -> bool:
    """Token-boundary membership test — avoids 'medium' matching 'med' (#122)."""
    toks = set(re.split(r"[-_.\s]", name_low))
    for w in words:
        if w.startswith("-"):          # explicit substring probe (callers pass '-vl')
            if w[1:] in name_low:
                return True
        elif w in toks:
            return True
    return False


def categorize(name: str, tags: Optional[List[str]] = None,
               pipeline_tag: Optional[str] = None) -> str:
    """Assign a capability category from the slug, card tags, and pipeline tag.

    Order matters: more specific buckets are tested first so e.g. ``medgemma``
    lands in MEDICAL, not REASONING. Falls back to GENERAL (plain chat).
    """
    low = name.lower()
    tagblob = " ".join(tags or []).lower()

    if pipeline_tag in VISION_PIPELINES or _has_word(low, "vl", "-vl", "vision", "multimodal", "omni"):
        return CAT_VISION
    if _has_word(low, "guard", "safeguard", "guardian", "moderation", "shield", "shieldgemma"):
        return CAT_SAFETY
    if _has_word(low, "medgemma", "medical", "clinical", "biomed", "biogpt"):
        return CAT_MEDICAL
    if _has_word(low, "coder", "code", "codegemma", "starcoder", "devstral"):
        return CAT_CODE
    if _has_word(low, "math", "prover", "theorem", "mathstral"):
        return CAT_MATH
    if (_has_word(low, "reasoning", "think", "thinking", "qwq", "openreasoning", "acereason")
            or "-r1" in low or "reasoning" in tagblob):
        return CAT_REASONING
    if _has_word(low, "function", "functiongemma", "-tool", "toolcall"):
        return CAT_FUNCTION
    return CAT_GENERAL


# Some MoE / multimodal repos report a wildly wrong safetensors.total (e.g. a
# "31B" assistant model reporting 0.47B). If the slug states an explicit size and
# it disagrees by more than this factor, trust the slug.
_PARAM_SANITY_RATIO = 2.5


def _slug_param_b(slug: str) -> Optional[float]:
    """Best-effort billions-of-params parsed from a slug (e.g. '7b'→7.0, '270m'→0.27)."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*([bm])\b", slug.lower())
    if not m:
        return None
    val = float(m.group(1))
    return val if m.group(2) == "b" else round(val / 1000.0, 3)


def param_size_billions(safetensors_total: Optional[int], slug: str,
                        default: float = 7.0) -> float:
    """Real parameter count in billions, preferring ``safetensors.total``.

    ``safetensors.total`` (from list/model_info ``expand``) is the authoritative
    element count of the full-precision base. Cross-checked against the slug: if
    both exist and disagree beyond ``_PARAM_SANITY_RATIO`` (bogus MoE/VLM totals),
    the slug wins; if only one exists, use it; else ``default``.
    """
    st_b = round(safetensors_total / 1e9, 2) if safetensors_total else None
    slug_b = _slug_param_b(slug)
    if st_b and slug_b:
        hi, lo = max(st_b, slug_b), min(st_b, slug_b)
        if lo > 0 and hi / lo > _PARAM_SANITY_RATIO:
            return slug_b
        return st_b
    if st_b:
        return st_b
    if slug_b:
        return slug_b
    return default
