"""GFM Markdown table helpers."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence


def escape_cell(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = s.split("\n")
    flattened = " ".join(line.strip() for line in lines if line is not None)
    return flattened.replace("|", "\\|")


def table_to_markdown(rows: Optional[Sequence[Sequence[Any]]]) -> str:
    """Render a rectangular matrix as a GitHub-flavored Markdown table."""
    if not rows:
        return ""
    data: List[List[str]] = []
    max_cols = 0
    for row in rows:
        if row is None:
            continue
        cells = [escape_cell(c) for c in row]
        max_cols = max(max_cols, len(cells))
        data.append(cells)
    if not data:
        return ""
    for r in data:
        while len(r) < max_cols:
            r.append("")
    header = data[0]
    body = data[1:] if len(data) > 1 else []
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in range(max_cols)) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"
