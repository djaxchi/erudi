"""Markdown rendering helpers shared by the Tier-0 extractors."""

from __future__ import annotations


def rows_to_markdown_table(rows: list[list[str]]) -> str:
    """Render rows as a GitHub-style Markdown table (first row = header).

    Cells are flattened (newlines → spaces) and pipes escaped so the table
    survives the Markdown-header chunking pass intact.
    """
    if not rows:
        return ""
    width = max(len(row) for row in rows)

    def fmt(row: list[str]) -> str:
        cells = [
            str(cell).replace("|", "\\|").replace("\n", " ").strip()
            for cell in row
        ]
        cells += [""] * (width - len(cells))
        return "| " + " | ".join(cells) + " |"

    header, *body = rows
    lines = [fmt(header), "| " + " | ".join(["---"] * width) + " |"]
    lines += [fmt(row) for row in body]
    return "\n".join(lines)
