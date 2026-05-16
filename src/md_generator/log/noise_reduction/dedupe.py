from __future__ import annotations

import hashlib

from md_generator.log.parser.models import LogRecord


def record_fingerprint(r: LogRecord) -> str:
    key = f"{r.level}|{r.logger}|{r.message}"
    return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()[:16]


def dedupe_records(records: list[LogRecord]) -> list[LogRecord]:
    seen: set[str] = set()
    out: list[LogRecord] = []
    for r in records:
        fp = record_fingerprint(r)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(r)
    return out
