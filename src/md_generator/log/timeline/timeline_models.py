from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from md_generator.log.parser.models import LogRecord


@dataclass(slots=True)
class TimelineEvent:
    timestamp: datetime | None
    label: str
    level: str
    record: LogRecord
