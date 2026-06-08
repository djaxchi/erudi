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
