from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class IncidentOccurrence:
    timestamp: datetime | None
    level: str
    message: str
    source_file: Path
    line_number: int
    stacktrace: str | None = None
    logger: str | None = None


@dataclass(slots=True)
class IncidentSummary:
    incident_id: str
    title: str
    occurrences: int
    severity: float
    first_seen: datetime | None
    last_seen: datetime | None
    fingerprint: str


@dataclass(slots=True)
class Incident:
    incident_id: str
    title: str
    fingerprint: str
    severity: float
    occurrences: list[IncidentOccurrence] = field(default_factory=list)
    representative_messages: list[str] = field(default_factory=list)
    stacktraces: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)

    @property
    def first_seen(self) -> datetime | None:
        ts = [o.timestamp for o in self.occurrences if o.timestamp is not None]
        return min(ts) if ts else None

    @property
    def last_seen(self) -> datetime | None:
        ts = [o.timestamp for o in self.occurrences if o.timestamp is not None]
        return max(ts) if ts else None
