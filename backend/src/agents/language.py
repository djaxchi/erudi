"""Question-language detection for the KB prompt's answer-language line.

Multilingual RAG drifts toward English (the "semantic attractor" — measured
in the language-drift literature), and a generic "same language" line is the
weakest counter-measure. The strongest prompt-level move is a dynamic
instruction written IN the target language ("Réponds en français."), which
needs the question's language: py3langid (resident ~2 MB model, BSD), with
a confidence floor so short/ambiguous turns fall back to the generic line
instead of guessing.
"""

from __future__ import annotations

from typing import Optional

from py3langid.langid import MODEL_FILE, LanguageIdentifier

# Below this normalized probability the signal is noise ("ok" scores ~0.17):
# the caller falls back to the generic same-language instruction.
MIN_CONFIDENCE = 0.7

_identifier: Optional[LanguageIdentifier] = None


def _get_identifier() -> LanguageIdentifier:
    """Resident classifier (lazy singleton — same pattern as E5Embeddings)."""
    global _identifier
    if _identifier is None:
        _identifier = LanguageIdentifier.from_pickled_model(
            MODEL_FILE, norm_probs=True
        )
    return _identifier


def detect_language(text: str) -> Optional[str]:
    """ISO 639-1 code of ``text``'s language, or None when unconfident."""
    text = (text or "").strip()
    if not text:
        return None
    language, probability = _get_identifier().classify(text)
    return language if probability >= MIN_CONFIDENCE else None
