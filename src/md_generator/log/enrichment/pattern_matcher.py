from __future__ import annotations

import re
from dataclasses import replace

from md_generator.log.parser.models import LogRecord

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("auth_failure", re.compile(r"auth(entication)?\s+failed|invalid\s+(credentials|token)|\b401\b|unauthorized", re.I)),
    ("sql_error", re.compile(r"\bORA-\d+|syntax error|SQLITE_\w+|PostgreSQL|deadlock", re.I)),
    ("permission", re.compile(r"permission denied|forbidden|\b403\b|access denied", re.I)),
    ("timeout", re.compile(r"timeout|timed out|Read timed out", re.I)),
    ("network", re.compile(r"connection refused|ECONNRESET|host unreachable|network error", re.I)),
]


def tag_patterns(record: LogRecord) -> LogRecord:
    text = record.message + "\n" + (record.stacktrace or "")
    tags = [name for name, rx in _PATTERNS if rx.search(text)]
    if not tags:
        return record
    md = dict(record.metadata)
    md["pattern_tags"] = tags
    return replace(record, metadata=md)
