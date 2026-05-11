from __future__ import annotations

import re

_LEVEL_SCAN = re.compile(
    r"\b(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\b",
    re.IGNORECASE,
)


def scan_level(text: str) -> str | None:
    m = _LEVEL_SCAN.search(text)
    if not m:
        return None
    lvl = m.group(1).upper()
    if lvl == "WARNING":
        return "WARN"
    return lvl


def message_without_level(text: str) -> str:
    m = _LEVEL_SCAN.search(text)
    if not m:
        return text.strip()
    return (text[: m.start()] + text[m.end() :]).strip()
