"""Plain-text / Markdown extractor.

``.md`` files are already the pipeline's pivot format — cleaned passthrough
(headers intact for the chunker). ``.txt`` gets the same non-destructive
cleaning. UTF-8 first, latin-1 fallback for legacy files.
"""

from __future__ import annotations

from pathlib import Path

from src.core.logging import logger
from src.ingestion.cleaning import clean_extracted_text
from src.ingestion.types import ExtractedDocument


class TextExtractor:
    def extract(self, path: Path) -> ExtractedDocument:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning(
                f"Text file {path.name}: not valid UTF-8 — "
                f"falling back to latin-1 decoding"
            )
            text = raw.decode("latin-1")
        logger.debug(f"Text extracted: {path.name} ({len(text)} chars)")

        return ExtractedDocument(
            markdown=clean_extracted_text(text),
            status="active",
            metadata={"extractor": "text"},
        )
