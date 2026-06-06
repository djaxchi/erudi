"""Plain-text / Markdown extractor.

``.md`` files are already the pipeline's pivot format — cleaned passthrough
(headers intact for the chunker). ``.txt`` gets the same non-destructive
cleaning. UTF-8 first, latin-1 fallback for legacy files.
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.cleaning import clean_extracted_text
from src.ingestion.types import ExtractedDocument


class TextExtractor:
    def extract(self, path: Path) -> ExtractedDocument:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")

        return ExtractedDocument(
            markdown=clean_extracted_text(text),
            status="active",
            metadata={"extractor": "text"},
        )
