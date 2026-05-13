from __future__ import annotations

import re

_TRACE = re.compile(r"\btrace[_-]?id[=:]?\s*([\w-]+)", re.I)
_SPAN = re.compile(r"\bspan[_-]?id[=:]?\s*([\w-]+)", re.I)


def parse_trace_fields(text: str) -> tuple[str | None, str | None]:
    tm = _TRACE.search(text)
    sm = _SPAN.search(text)
    return (tm.group(1) if tm else None, sm.group(1) if sm else None)
