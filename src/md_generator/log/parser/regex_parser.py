from __future__ import annotations

import re
from typing import Any

from md_generator.log.utils.regex import compile_optional


def try_structured_match(line: str, pattern: re.Pattern[str]) -> dict[str, str] | None:
    m = pattern.match(line)
    if not m:
        return None
    return {k: (v or "").strip() for k, v in m.groupdict().items()}


def default_line_regex() -> str:
    return (
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
        r"(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\s+"
        r"(?P<message>.*)$"
    )


def compiled_pattern(cfg_line_regex: str | None) -> re.Pattern[str]:
    pat = cfg_line_regex or default_line_regex()
    c = compile_optional(pat)
    assert c is not None
    return c
