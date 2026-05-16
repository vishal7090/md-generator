from __future__ import annotations

from md_generator.log.incidents.models import IncidentOccurrence

_LEVEL_SCORE = {
    "FATAL": 60.0,
    "ERROR": 50.0,
    "WARN": 40.0,
    "WARNING": 40.0,
    "INFO": 20.0,
    "DEBUG": 10.0,
    "TRACE": 5.0,
}


def score_occurrences(occurrences: list[IncidentOccurrence]) -> float:
    if not occurrences:
        return 0.0
    level_part = max(_LEVEL_SCORE.get(o.level.upper(), 25.0) for o in occurrences)
    count_part = min(len(occurrences) * 2.0, 40.0)
    return round(level_part + count_part, 2)
