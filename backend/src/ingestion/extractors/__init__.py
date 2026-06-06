"""Tier-0 deterministic extractors (one per document format).

Each extractor exposes ``extract(path) -> ExtractedDocument`` and is
registered on the ``DocumentReader`` façade by extension. The OCR/VLM tiers
of a later release plug in as additional extractors on the same façade.
"""

from src.ingestion.extractors.docx import DocxExtractor
from src.ingestion.extractors.pdf import PdfExtractor
from src.ingestion.extractors.tabular import CsvExtractor
from src.ingestion.extractors.text import TextExtractor
from src.ingestion.extractors.xlsx import XlsxExtractor

__all__ = [
    "CsvExtractor",
    "DocxExtractor",
    "PdfExtractor",
    "TextExtractor",
    "XlsxExtractor",
]
