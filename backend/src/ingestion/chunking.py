"""3-pass Markdown chunking, token-accurate against the real e5 tokenizer.

Ported from the R&D ingestion POC and re-targeted at multilingual-e5-small:

1. Split on Markdown headers (h1–h4) — chunks follow document structure.
2. Sub-split large sections with a token-accurate recursive splitter
   (separators favor paragraph > line > sentence > word boundaries). The
   FAISS-era chunker estimated ~3 chars/token against a model truncating at
   128 tokens — two thirds of every chunk was invisible to dense retrieval.
3. Prefix each chunk with its heading breadcrumb ("# A > ## B") and
   re-attach Markdown table headers lost mid-split.

Budget [N6]: the full embedded text is
``passage: [document_name:NAME]\\n<breadcrumb>\\n\\n<chunk>``; with the
default target (~180 tokens) plus breadcrumb and name the total stays far
inside e5's 512-token window. The R&D sweeps found 150–200-token chunks the
most consistent — big chunks measurably HURT dense retrieval.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.core import config
from src.core.logging import logger
from src.ingestion.types import ExtractedDocument

E5_TOKENIZER_NAME = "intfloat/multilingual-e5-small"

DEFAULT_TARGET_TOKENS = 180
DEFAULT_OVERLAP_TOKENS = 27  # ~15 %

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]

_tokenizer = None
_tokenizer_lock = threading.Lock()


def _get_tokenizer():
    """Lazy resident e5 tokenizer (a few MB, fetched from the HF cache)."""
    global _tokenizer
    if _tokenizer is None:
        with _tokenizer_lock:
            if _tokenizer is None:
                from transformers import AutoTokenizer

                # Same repo as the embedding model, pinned to CACHE_DIR so the
                # single #146 download serves both consumers (no 2nd fetch).
                _tokenizer = AutoTokenizer.from_pretrained(
                    E5_TOKENIZER_NAME, cache_dir=str(config.CACHE_DIR)
                )
    return _tokenizer


def count_tokens(text: str) -> int:
    """Real e5 subword count (no special tokens) — never a chars/N estimate."""
    return len(_get_tokenizer().encode(text, add_special_tokens=False))


@dataclass(slots=True)
class Chunk:
    """One retrieval unit, ready for ``build_embedding_text`` + embedding."""

    chunk_index: int
    text: str
    token_count: int
    page_number: int | None = None


def _heading_breadcrumb(metadata: dict[str, str]) -> str:
    parts: list[str] = []
    for key in ("h1", "h2", "h3", "h4"):
        if key in metadata:
            level = int(key[1])
            parts.append(f"{'#' * level} {metadata[key]}")
    return " > ".join(parts)


def _reattach_table_headers(chunks: list[str]) -> list[str]:
    """Re-inject the Markdown table header into sub-chunks that lost it."""
    if not chunks:
        return chunks

    table_header: str | None = None
    result: list[str] = []

    for chunk in chunks:
        lines = chunk.split("\n")

        # Scan for a table header (header row + separator row) in this chunk.
        found_header = False
        for i in range(len(lines) - 1):
            line = lines[i].strip()
            next_line = lines[i + 1].strip()
            if (
                line.startswith("|")
                and line.endswith("|")
                and next_line.startswith("|")
                and "---" in next_line
            ):
                table_header = lines[i] + "\n" + lines[i + 1]
                found_header = True
                break

        if found_header:
            result.append(chunk)
            continue

        first_content = next((ln.strip() for ln in lines if ln.strip()), "")

        if first_content.startswith("|") and table_header is not None:
            # Headerless continuation of the running table.
            prefix_lines: list[str] = []
            rest_lines: list[str] = []
            in_prefix = True
            for line in lines:
                if in_prefix and not line.strip().startswith("|"):
                    prefix_lines.append(line)
                else:
                    in_prefix = False
                    rest_lines.append(line)
            if prefix_lines:
                result.append(
                    "\n".join(prefix_lines) + "\n" + table_header + "\n" + "\n".join(rest_lines)
                )
            else:
                result.append(table_header + "\n" + chunk)
        else:
            if not first_content.startswith("|"):
                table_header = None
            result.append(chunk)

    return result


def _make_sub_splitter(target_tokens: int, overlap_tokens: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        _get_tokenizer(),
        chunk_size=target_tokens,
        chunk_overlap=overlap_tokens,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def chunk_markdown(
    text: str,
    *,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    page_number: int | None = None,
    start_index: int = 0,
) -> list[Chunk]:
    """Run the 3-pass chunker over one Markdown text. See module docstring."""
    if not text or not text.strip():
        return []

    # PostgreSQL text columns reject NUL bytes; some parsers emit them.
    text = text.replace("\x00", "")

    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    sub_splitter = _make_sub_splitter(target_tokens, overlap_tokens)

    chunks: list[Chunk] = []
    for section in md_splitter.split_text(text):
        breadcrumb = _heading_breadcrumb(section.metadata)

        sub_texts = sub_splitter.split_text(section.page_content)
        sub_texts = _reattach_table_headers(sub_texts)

        for sub_text in sub_texts:
            chunk_text = f"{breadcrumb}\n\n{sub_text}" if breadcrumb else sub_text

            chunks.append(
                Chunk(
                    chunk_index=start_index + len(chunks),
                    text=chunk_text,
                    token_count=count_tokens(chunk_text),
                    page_number=page_number,
                )
            )

    return chunks


def chunk_document(
    document: ExtractedDocument,
    *,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Chunk an ``ExtractedDocument`` — page by page when paginated (PDF),
    so each chunk carries its ``page_number``; whole-Markdown otherwise.

    ``pending_vision`` documents yield no chunks (indexed by the OCR/VLM
    tiers of a later release).
    """
    if document.status != "active":
        return []

    if document.pages:
        chunks: list[Chunk] = []
        for page in document.pages:
            chunks.extend(
                chunk_markdown(
                    page.text,
                    target_tokens=target_tokens,
                    overlap_tokens=overlap_tokens,
                    page_number=page.page_number,
                    start_index=len(chunks),
                )
            )
    else:
        chunks = chunk_markdown(
            document.markdown,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )

    if chunks:
        avg_tokens = sum(chunk.token_count for chunk in chunks) / len(chunks)
        logger.info(
            f"Document chunked: {len(chunks)} chunks, "
            f"avg {avg_tokens:.0f} tokens/chunk "
            f"(extractor={document.metadata.get('extractor', '?')})"
        )
    else:
        logger.debug(
            f"Document chunked: 0 chunks "
            f"(extractor={document.metadata.get('extractor', '?')})"
        )
    return chunks
