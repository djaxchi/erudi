"""PR3 — question-language detection for the KB prompt (issue #81, problem #3).

Real py3langid model (resident singleton, ~2 MB): a localized, dynamic
"answer in <language>" instruction measurably beats the generic line, but
only when detection is confident — short/ambiguous inputs must fall back
to None so the prompt uses the generic instruction instead of guessing.
"""

import pytest

from src.agents.language import detect_language

pytestmark = pytest.mark.unit


class TestDetectLanguage:
    def test_detects_french(self):
        assert detect_language("Quel est le préavis de résiliation du contrat ?") == "fr"

    def test_detects_english(self):
        assert detect_language("What is the notice period for termination?") == "en"

    def test_detects_german(self):
        assert detect_language("Wie hoch ist die Vertragsstrafe für den Anbieter?") == "de"

    def test_short_followup_with_clear_signal_is_detected(self):
        # Accented stopwords give py3langid full confidence even on 4 words.
        assert detect_language("Et le préavis ?") == "fr"

    def test_ambiguous_input_returns_none(self):
        assert detect_language("ok") is None

    def test_empty_and_whitespace_return_none(self):
        assert detect_language("") is None
        assert detect_language("   ") is None


class TestDetectLanguageDegradesGracefully:
    """A missing/unreadable langid model must NOT crash a query.

    Packaging regression (bug 6): py3langid's model.plzma was not bundled, so
    the systematic KB path (build_kb_context_block -> detect_language) died with
    FileNotFoundError. Beyond bundling the data file, detection must degrade to
    None (generic answer-language line) rather than propagate the error.
    """

    def test_returns_none_when_model_fails_to_load(self, monkeypatch):
        import src.agents.language as language

        # Force a fresh, failing load.
        monkeypatch.setattr(language, "_identifier", None, raising=False)
        monkeypatch.setattr(language, "_load_failed", False, raising=False)

        def _boom(*_a, **_k):
            raise FileNotFoundError("model.plzma")

        monkeypatch.setattr(
            language.LanguageIdentifier, "from_pickled_model", staticmethod(_boom)
        )
        # Must not raise, and must fall back to the generic line (None).
        assert language.detect_language("Quelle est la capitale de la France ?") is None

    def test_load_failure_is_cached_not_retried(self, monkeypatch):
        import src.agents.language as language

        monkeypatch.setattr(language, "_identifier", None, raising=False)
        monkeypatch.setattr(language, "_load_failed", False, raising=False)
        calls = {"n": 0}

        def _boom(*_a, **_k):
            calls["n"] += 1
            raise OSError("unreadable")

        monkeypatch.setattr(
            language.LanguageIdentifier, "from_pickled_model", staticmethod(_boom)
        )
        assert language.detect_language("Bonjour le monde") is None
        assert language.detect_language("Hello world again") is None
        assert calls["n"] == 1  # the failed load is attempted once, then cached
