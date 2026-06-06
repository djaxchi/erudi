"""Non-destructive text cleaning for extracted documents (D4).

The FAISS-era cleaner stripped accents and non-ASCII characters, which made
the indexed corpus diverge from raw user queries and would have killed the
sparse (tsvector) branch of hybrid retrieval outright. This cleaner only
removes what carries no meaning:

- Unicode NFC normalization (precompose combining accents),
- NUL bytes (PostgreSQL text columns reject them) and other control/format
  characters — newlines and tabs excepted,
- PDF end-of-line hyphenation rejoined ("informa-\\ntion" → "information"),
- whitespace collapsed (runs of spaces/tabs → one space, 3+ newlines → a
  paragraph break).

Accents, currency signs, CJK — everything meaningful — are PRESERVED.
"""

from __future__ import annotations

import re
import unicodedata

# "informa-\ntion" → "information". Dictionary-less heuristic: a genuine
# compound split at end of line ("peut-\nêtre") is rejoined too — rare and
# harmless next to the constant hyphenation noise of justified PDF text.
_HYPHENATION_RE = re.compile(r"(\w)-\n(?=\w)", re.UNICODE)
_HORIZONTAL_WS_RE = re.compile(r"[ \t]+")
_NEWLINE_TRIM_RE = re.compile(r" ?\n ?")
_PARAGRAPH_RE = re.compile(r"\n{3,}")


def _keep(ch: str) -> bool:
    if ch in ("\n", "\t"):
        return True
    # Drop Cc (control) and Cf (format: zero-width, soft hyphen, …).
    return unicodedata.category(ch)[0] != "C"


def clean_extracted_text(text: str) -> str:
    """Clean extracted text without destroying meaning. See module docstring."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHENATION_RE.sub(r"\1", text)
    text = "".join(ch for ch in text if _keep(ch))
    text = _HORIZONTAL_WS_RE.sub(" ", text)
    text = _NEWLINE_TRIM_RE.sub("\n", text)
    text = _PARAGRAPH_RE.sub("\n\n", text)
    return text.strip()
