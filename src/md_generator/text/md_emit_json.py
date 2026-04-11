from __future__ import annotations

import json
import re
from typing import Any, List


def _title_key(key: str) -> str:
    s = key.replace("_", " ").replace("-", " ")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return s.strip().title() or key


def _heading_prefix(level: int) -> str:
    level = max(2, min(6, level))
    return "#" * level


def _slug(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"[\s_]+", "-", t)
    return t or "section"


def _homogeneous_object_list(items: list[Any]) -> bool:
    if not items:
        return False
    if not all(isinstance(x, dict) for x in items):
        return False
    dicts: list[dict[str, Any]] = [x for x in items if isinstance(x, dict)]
    if not dicts:
        return False
    keys0 = set(dicts[0].keys())
    return all(set(d.keys()) == keys0 for d in dicts)


def _escape_cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def _json_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _emit_table(rows: list[dict[str, Any]], out: List[str]) -> None:
    keys = list(rows[0].keys()) if rows else []
    if not keys:
        return
    headers = [_title_key(k) for k in keys]
    out.append("")
    out.append("| " + " | ".join(_escape_cell(h) for h in headers) + " |")
    out.append("| " + " | ".join("---" for _ in keys) + " |")
    for row in rows:
        cells = [_escape_cell(_json_cell(row.get(k))) for k in keys]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")


def _emit_value(
    key: str | None,
    value: Any,
    level: int,
    out: List[str],
    toc: List[tuple[str, str]],
) -> None:
    if isinstance(value, dict):
        if key is not None:
            title = _title_key(key)
            hp = _heading_prefix(level)
            out.append("")
            out.append(f"{hp} {title}")
            toc.append((title, _slug(title)))
            next_level = level + 1
        else:
            next_level = level
        for k, v in value.items():
            _emit_value(k, v, next_level, out, toc)
        return

    if isinstance(value, list):
        if key is not None:
            title = _title_key(key)
            hp = _heading_prefix(level)
            out.append("")
            out.append(f"{hp} {title}")
            toc.append((title, _slug(title)))
        if _homogeneous_object_list(value):
            _emit_table(value, out)  # type: ignore[arg-type]
        else:
            for item in value:
                if isinstance(item, dict):
                    out.append("")
                    _emit_value(None, item, level + (1 if key is not None else 0), out, toc)
                else:
                    out.append(f"- {_json_cell(item)}")
            if value:
                out.append("")
        return

    if key is not None:
        out.append(f"- **{_title_key(key)}:** {_json_cell(value)}")


def json_to_markdown(obj: Any, raw_text: str, *, include_source_block: bool, generate_toc: bool) -> str:
    out: List[str] = []
    toc: List[tuple[str, str]] = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            _emit_value(k, v, 2, out, toc)
    elif isinstance(obj, list):
        _emit_value(None, obj, 2, out, toc)
    else:
        out.append("")
        out.append(f"- **Value:** {_json_cell(obj)}")
        out.append("")

    body = "\n".join(out)
    while "\n\n\n" in body:
        body = body.replace("\n\n\n", "\n\n")

    prefix = ""
    if generate_toc and toc:
        lines = ["## Table of contents", ""]
        for title, slug in toc:
            lines.append(f"- [{title}](#{slug})")
        lines.append("")
        prefix = "\n".join(lines)

    chunks: List[str] = []
    if prefix.strip():
        chunks.append(prefix.rstrip())
    if body.strip():
        chunks.append(body.strip())
    if include_source_block:
        chunks.append("```json")
        chunks.append(raw_text.rstrip())
        chunks.append("```")
    return "\n\n".join(chunks).strip() + "\n"
