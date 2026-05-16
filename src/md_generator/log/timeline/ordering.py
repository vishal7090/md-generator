from __future__ import annotations

from md_generator.log.parser.models import LogRecord
from md_generator.log.timeline.timeline_models import TimelineEvent


def order_events(records: list[LogRecord]) -> list[TimelineEvent]:
    events = [
        TimelineEvent(timestamp=r.timestamp, label=r.message[:200], level=r.level, record=r)
        for r in records
    ]
    return sorted(events, key=lambda e: (e.timestamp or e.record.line_number, e.record.line_number))
