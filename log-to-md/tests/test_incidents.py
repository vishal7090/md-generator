from __future__ import annotations

from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.incidents.incident_engine import build_incidents
from md_generator.log.incidents.severity import score_occurrences
from md_generator.log.parser.models import LogRecord


def _record(msg: str, level: str = "ERROR") -> LogRecord:
    return LogRecord(
        timestamp=None,
        level=level,
        logger="auth",
        thread=None,
        message=msg,
        raw_message=msg,
        stacktrace=None,
        source_file=Path("a.log"),
        line_number=1,
    )


def test_grouping_min_occurrences() -> None:
    cfg = LogRunConfig()
    records = [_record("Database connection failed")] * 3 + [_record("ok", "INFO")]
    inc = build_incidents(records, cfg)
    assert len(inc) >= 1
    assert inc[0].occurrences and len(inc[0].occurrences) == 3


def test_severity_scoring() -> None:
    from md_generator.log.incidents.models import IncidentOccurrence

    occ = [IncidentOccurrence(None, "ERROR", "x", Path("a"), 1)]
    assert score_occurrences(occ) >= 50.0
