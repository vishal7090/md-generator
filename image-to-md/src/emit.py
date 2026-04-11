"""Build Markdown from OCR results."""

from __future__ import annotations


def normalize_whitespace(text: str) -> str:
    """Strip trailing spaces per line; collapse consecutive blank lines to one."""
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    prev_blank = False
    for ln in lines:
        if not ln.strip():
            if not prev_blank:
                out.append("")
            prev_blank = True
        else:
            prev_blank = False
            out.append(ln)
    return "\n".join(out).strip()


def markdown_compare(title: str, sections: list[tuple[str, dict[str, str]]]) -> str:
    """
    sections: (image_filename, {engine_display_name: raw_text}).
    """
    parts: list[str] = [f"# {title}", ""]
    for filename, engine_texts in sections:
        parts.append(f"## {filename}")
        parts.append("")
        for engine_name, raw in engine_texts.items():
            parts.append(f"### {engine_name}")
            parts.append("")
            body = normalize_whitespace(raw)
            parts.append(body if body else "_No text extracted._")
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def markdown_best(title: str, sections: list[tuple[str, str]]) -> str:
    """sections: (image_filename, chosen_plain_text)."""
    parts: list[str] = [f"# {title}", ""]
    for filename, raw in sections:
        parts.append(f"## {filename}")
        parts.append("")
        body = normalize_whitespace(raw)
        parts.append(body if body else "_No text extracted._")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def pick_best_text(by_engine_name: dict[str, str], priority_engine_names: list[str]) -> str:
    """
    Choose the longest non-empty extraction; tie-break by earlier engine in user priority.
    """
    best = ""
    best_pri = len(priority_engine_names)
    best_len = -1
    for pri, name in enumerate(priority_engine_names):
        t = (by_engine_name.get(name) or "").strip()
        if not t:
            continue
        ln = len(t)
        if ln > best_len or (ln == best_len and pri < best_pri):
            best = t
            best_len = ln
            best_pri = pri
    return best
