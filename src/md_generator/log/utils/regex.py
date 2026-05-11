from __future__ import annotations

import re


def compile_optional(pattern: str | None) -> re.Pattern[str] | None:
    if not pattern or not str(pattern).strip():
        return None
    return re.compile(str(pattern), re.MULTILINE)
