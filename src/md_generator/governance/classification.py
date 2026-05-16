from __future__ import annotations

import re
from dataclasses import replace

from md_generator.log.parser.models import LogRecord

_PII = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_AUTH = re.compile(r"\b(unauthorized|forbidden|auth failed|login failed)\b", re.I)


def classify_records(records: list[LogRecord]) -> list[LogRecord]:
    out: list[LogRecord] = []
    for r in records:
        tags: list[str] = []
        msg = r.message or ""
        if _PII.search(msg):
            tags.append("pii_detected")
        if _AUTH.search(msg):
            tags.append("auth_failure")
        if tags:
            md = dict(r.metadata)
            existing = md.get("classification", [])
            if isinstance(existing, list):
                md["classification"] = sorted(set(existing) | set(tags))
            else:
                md["classification"] = tags
            out.append(replace(r, metadata=md))
        else:
            out.append(r)
    return out
