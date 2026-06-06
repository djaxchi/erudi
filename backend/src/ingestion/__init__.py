"""Document ingestion pipeline (extraction → cleaning → chunking → embeddings).

Public surface:
    - ``DocumentReader`` — the extraction façade services talk to.
    - ``ExtractedDocument`` / ``ExtractedPage`` — its return types.
"""

from src.ingestion.reader import DocumentReader
from src.ingestion.types import ExtractedDocument, ExtractedPage

__all__ = ["DocumentReader", "ExtractedDocument", "ExtractedPage"]
