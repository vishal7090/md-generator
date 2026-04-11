from __future__ import annotations

import re
from typing import List


def _escape_cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def _is_heading_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 2 or len(s) > 80:
        return False
    if not any(c.isalpha() for c in s):
        return False
    return s.upper() == s


def _is_numbered_heading(line: str) -> bool:
    return bool(re.match(r"^\d+[\.\)]\s+[A-Za-z].*", line.strip()))


def _kv_line(line: str) -> tuple[str, str] | None:
    s = line.strip()
    m = re.match(r"^([^:=]+?)\s*[:=]\s*(.+)$", s)
    if not m:
        return None
    k, v = m.group(1).strip(), m.group(2).strip()
    if not k or not v:
        return None
    return k, v


def txt_to_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")
    out: List[str] = []
    i = 0
    kv_run: list[tuple[str, str]] = []

    def flush_kv() -> None:
        nonlocal kv_run
        if not kv_run:
            return
        out.append("")
        out.append("| Key | Value |")
        out.append("| --- | --- |")
        for k, v in kv_run:
            out.append(f"| {_escape_cell(k)} | {_escape_cell(v)} |")
        out.append("")
        kv_run = []

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            flush_kv()
            out.append("")
            i += 1
            continue

        kv = _kv_line(raw)
        if kv:
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt and _kv_line(lines[i + 1]) is not None:
                kv_run.append(kv)
                i += 1
                continue
            if kv_run:
                kv_run.append(kv)
                flush_kv()
                i += 1
                continue

        flush_kv()

        if re.match(r"^[\-\*•]\s+", stripped):
            out.append(f"- {stripped[1:].lstrip('•').strip()}")
            i += 1
            continue

        if re.match(r"^\d+[\.\)]\s+", stripped) and not _is_numbered_heading(raw):
            item = re.sub(r"^\d+[\.\)]\s+", "", stripped)
            out.append(f"- {item}")
            i += 1
            continue

        if _is_heading_line(stripped):
            level = "##" if len(stripped) > 40 else "#"
            out.append("")
            out.append(f"{level} {stripped.title()}")
            out.append("")
            i += 1
            continue

        if _is_numbered_heading(raw):
            title = re.sub(r"^\d+[\.\)]\s+", "", stripped)
            out.append("")
            out.append(f"## {title}")
            out.append("")
            i += 1
            continue

        out.append(stripped)
        i += 1

    flush_kv()
    result = "\n".join(line.rstrip() for line in out)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result.strip() + "\n"
