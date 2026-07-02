"""DocumentReader — the single extraction surface seen by services.

Two-dimensional routing:
  1. By document TYPE (extension): pdf, docx, xlsx, csv, txt, md → the
     matching Tier-0 deterministic extractor; png/jpg/jpeg/webp → accepted
     as ``pending_vision`` (no OCR/VLM tier bundled yet).
  2. By DIFFICULTY, inside the PDF extractor: native text layer →
     deterministic fast-path; scanned → ``pending_vision``.

Services stay 100 % agnostic: ``read(path) -> ExtractedDocument`` is the
whole contract. Later OCR/VLM tiers register as additional extractors on
this façade without touching any caller.

Naming note: "Engine" is reserved for inference engines in Erudi — this is
a *reader* backed by *extractors*.
"""

from __future__ import annotations

from pathlib import Path

from src.core.exceptions import InvalidInputException
from src.core.logging import logger
from src.ingestion.extractors import (
    CsvExtractor,
    DocxExtractor,
    PdfExtractor,
    TextExtractor,
    XlsxExtractor,
)
from src.ingestion.types import ExtractedDocument

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class DocumentReader:
    """Route a file to its extractor and return an ``ExtractedDocument``."""

    def __init__(self) -> None:
        text_extractor = TextExtractor()
        self._extractors = {
            ".pdf": PdfExtractor(),
            ".docx": DocxExtractor(),
            ".xlsx": XlsxExtractor(),
            ".csv": CsvExtractor(),
            ".txt": text_extractor,
            ".md": text_extractor,
        }

    @property
    def supported_extensions(self) -> set[str]:
        return set(self._extractors) | IMAGE_EXTENSIONS

    def read(self, path: Path | str) -> ExtractedDocument:
        """Extract one document. Raises ``InvalidInputException`` on
        unsupported extensions; never raises on images (``pending_vision``)."""
        path = Path(path)
        extension = path.suffix.lower()

        if extension in IMAGE_EXTENSIONS:
            logger.info(
                f"Document read: {path.name} (format={extension}, "
                f"status=pending_vision, chars=0)"
            )
            return ExtractedDocument(
                markdown="",
                status="pending_vision",
                metadata={
                    "extractor": "image",
                    "reason": "image awaiting OCR/VLM tier",
                },
            )

        extractor = self._extractors.get(extension)
        if extractor is None:
            supported = ", ".join(sorted(self.supported_extensions))
            raise InvalidInputException(
                f"Unsupported document type '{extension}' ({path.name}). "
                f"Supported: {supported}"
            )

        document = extractor.extract(path)
        logger.info(
            f"Document read: {path.name} (format={extension}, "
            f"status={document.status}, chars={len(document.markdown)})"
        )
        return document
