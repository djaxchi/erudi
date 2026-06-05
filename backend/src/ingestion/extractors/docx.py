"""DOCX extractor — python-docx, structure-preserving.

Heading styles map to Markdown headers (Heading 1 → ``#`` … Heading 4 →
``####``) so the 3-pass chunker can split on real document structure;
tables become Markdown tables. Paragraphs and tables are walked in document
order via ``Document.iter_inner_content``.
"""

from __future__ import annotations

import re
from pathlib import Path

import docx
from docx.table import Table

from src.ingestion.cleaning import clean_extracted_text
from src.ingestion.markdown import rows_to_markdown_table
from src.ingestion.types import ExtractedDocument

_HEADING_STYLE_RE = re.compile(r"^Heading (\d)$")


def _heading_prefix(style_name: str | None) -> str:
    match = _HEADING_STYLE_RE.match(style_name or "")
    if not match:
        return ""
    level = min(int(match.group(1)), 4)
    return "#" * level + " "


class DocxExtractor:
    def extract(self, path: Path) -> ExtractedDocument:
        document = docx.Document(str(path))
        parts: list[str] = []

        for item in document.iter_inner_content():
            if isinstance(item, Table):
                rows = [
                    [cell.text for cell in row.cells]
                    for row in item.rows
                ]
                table = rows_to_markdown_table(rows)
                if table:
                    parts.append(table)
                continue

            text = item.text.strip()
            if not text:
                continue
            parts.append(_heading_prefix(item.style.name) + text)

        markdown = clean_extracted_text("\n\n".join(parts))
        return ExtractedDocument(
            markdown=markdown,
            status="active",
            metadata={"extractor": "docx"},
        )
