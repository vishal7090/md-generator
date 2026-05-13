from __future__ import annotations

from collections import defaultdict

from md_generator.log.incidents.fingerprinting import incident_fingerprint
from md_generator.log.incidents.models import IncidentOccurrence
from md_generator.log.parser.models import LogRecord


def group_records(
    records: list[LogRecord],
    *,
    min_occurrences: int,
    levels: frozenset[str] | None,
    stacktrace_aware: bool,
) -> dict[str, list[LogRecord]]:
    buckets: dict[str, list[LogRecord]] = defaultdict(list)
    for r in records:
        if levels and r.level.upper() not in levels:
            continue
        fp = incident_fingerprint(r, stacktrace_aware=stacktrace_aware)
        buckets[fp].append(r)
    return {k: v for k, v in buckets.items() if len(v) >= min_occurrences}
