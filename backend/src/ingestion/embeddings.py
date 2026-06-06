"""E5Embeddings — resident multilingual-e5-small behind the LangChain
``Embeddings`` interface.

multilingual-e5-small (384d, MIT, 512-token window) REQUIRES asymmetric
prefixes: ``query: `` for searches, ``passage: `` for indexed chunks —
without them retrieval quality collapses. sentence-transformers handles
mean pooling; vectors are L2-normalized so cosine similarity is a plain
dot product (pgvector COSINE / HNSW friendly).

The model is a RESIDENT class-level singleton: the FAISS-era embedder
reloaded ~470 MB from disk on every single operation and freed it after.

Embedded-text format [N6], frozen:
    ``passage: [document_name:<file>]\\n<breadcrumb>\\n\\n<chunk>``
(``passage: `` added here; ``[document_name:…]`` by ``build_embedding_text``;
breadcrumb by the chunker.)
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, ClassVar

from langchain_core.embeddings import Embeddings

from src.core.logging import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sentence_transformers import SentenceTransformer

E5_MODEL_NAME = "intfloat/multilingual-e5-small"
EMBEDDING_DIMENSIONS = 384


def build_embedding_text(*, file_name: str, chunk_text: str) -> str:
    """Prefix the chunk with its source document name (R&D POC format)."""
    return f"[document_name:{file_name}]\n{chunk_text}"


class E5Embeddings(Embeddings):
    """LangChain ``Embeddings`` over a resident e5-small singleton."""

    _model: ClassVar["SentenceTransformer | None"] = None
    _model_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def _get_model(cls) -> "SentenceTransformer":
        if cls._model is None:
            with cls._model_lock:
                if cls._model is None:
                    from sentence_transformers import SentenceTransformer

                    logger.info(f"Loading embedding model {E5_MODEL_NAME} (resident)")
                    cls._model = SentenceTransformer(E5_MODEL_NAME)
        return cls._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed indexed chunks (``passage: `` prefix, L2-normalized)."""
        vectors = self._get_model().encode(
            [f"passage: {text}" for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (``query: `` prefix, L2-normalized)."""
        vector = self._get_model().encode(
            [f"query: {text}"],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return vector.tolist()
