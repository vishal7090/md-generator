from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

Alignment = Literal["left", "right", "center"]


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        if value == int(value):
            return str(int(value))
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else str(value)
    if isinstance(value, bool):
        return str(value)
    s = str(value).strip()
    return s


def _escape_md_table_cell(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _row_all_empty(cells: list[str]) -> bool:
    return all(c == "" for c in cells)


def resolve_column_indices(
    header_row: list[str],
    column_names: list[str] | None,
    column_indices: list[int] | None,
) -> list[int] | None:
    if column_names:
        norm_header = [h.strip().casefold() for h in header_row]
        idxs: list[int] = []
        for name in column_names:
            target = name.strip().casefold()
            try:
                idxs.append(norm_header.index(target))
            except ValueError:
                raise ValueError(f"Column name not found in header row: {name!r}") from None
        if column_indices:
            allowed = set(column_indices)
            idxs = [i for i in idxs if i in allowed]
        return idxs
    if column_indices is not None:
        return list(column_indices)
    return None


def filter_row(row: list[Any], indices: list[int] | None, width: int) -> list[str]:
    texts = [_cell_text(row[i] if i < len(row) else None) for i in range(width)]
    if indices is None:
        while texts and texts[-1] == "":
            texts.pop()
        if not texts:
            return []
        return texts
    out: list[str] = []
    for i in indices:
        out.append(texts[i] if i < len(texts) else "")
    return out


def alignment_row(
    num_cols: int,
    alignments: list[Alignment],
    enable: bool,
) -> str | None:
    if not enable or num_cols == 0:
        return None
    parts: list[str] = []
    for c in range(num_cols):
        a = alignments[c] if c < len(alignments) else "left"
        if a == "left":
            parts.append(":---")
        elif a == "right":
            parts.append("---:")
        else:
            parts.append(":---:")
    return "| " + " | ".join(parts) + " |"


def rows_to_gfm_table(
    rows: list[list[Any]],
    *,
    column_names: list[str] | None = None,
    column_indices: list[int] | None = None,
    column_alignment: list[Alignment] | None = None,
    enable_alignment_in_tables: bool = False,
) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    padded = [list(r) + [None] * (width - len(r)) for r in rows]

    header_cells = [_cell_text(x) for x in padded[0]]
    indices = resolve_column_indices(header_cells, column_names, column_indices)

    body_rows: list[list[str]] = []
    for raw in padded:
        body_rows.append(filter_row(raw, indices, width))

    body_rows = [r for r in body_rows if not _row_all_empty(r)]
    if not body_rows:
        return ""

    lines: list[str] = []
    aligns = column_alignment or []
    for br in body_rows:
        esc = [_escape_md_table_cell(c) for c in br]
        lines.append("| " + " | ".join(esc) + " |")
        if len(lines) == 1:
            sep = alignment_row(len(br), aligns, enable_alignment_in_tables)
            if sep:
                lines.append(sep)
            else:
                lines.append("| " + " | ".join(["---"] * len(br)) + " |")

    return "\n".join(lines)


def slugify_sheet_title(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "sheet"


def safe_filename_slug(title: str) -> str:
    base = slugify_sheet_title(title)
    base = re.sub(r'[<>:"/\\|?*]', "-", base)
    return base or "sheet"
