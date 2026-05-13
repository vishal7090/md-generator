from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from md_generator.log.parser.models import LogRecord


@dataclass(slots=True)
class TraceLink:
    trace_id: str
    span_id: str | None
    records: list[LogRecord] = field(default_factory=list)


@dataclass(slots=True)
class CorrelatedRequest:
    request_id: str
    correlation_id: str | None
    session_id: str | None
    records: list[LogRecord] = field(default_factory=list)

    @property
    def first_seen(self) -> datetime | None:
        ts = [r.timestamp for r in self.records if r.timestamp]
        return min(ts) if ts else None

    @property
    def last_seen(self) -> datetime | None:
        ts = [r.timestamp for r in self.records if r.timestamp]
        return max(ts) if ts else None
