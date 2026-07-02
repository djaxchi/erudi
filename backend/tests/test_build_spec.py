"""Text-level guards on the PyInstaller spec.

The spec only executes under PyInstaller (it needs injected globals like
SPECPATH), so these tests assert on its text — cheap tripwires for
hidden-import regressions that otherwise only surface on a packaged build.
"""

from pathlib import Path

import pytest

SPEC = Path(__file__).parent.parent / "backend.spec"


@pytest.mark.unit
def test_spec_ships_the_gguf_package():
    # transformers imports `gguf` LAZILY (AutoTokenizer(gguf_file=...)), which is
    # invisible to PyInstaller's static analysis. Dropping this hiddenimport
    # silently breaks tool-calling detection for every GGUF model in frozen
    # builds — and with it the agentic KB mode (#171).
    text = SPEC.read_text(encoding="utf-8")
    assert '"gguf"' in text, "backend.spec must keep the 'gguf' hiddenimport (#171)"
