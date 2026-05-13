from __future__ import annotations

from md_generator.log.parser.models import LogRecord


def repeated_spike(records: list[LogRecord], keyword: str, *, min_count: int = 3) -> bool:
    c = sum(1 for r in records if keyword.lower() in r.message.lower())
    return c >= min_count
