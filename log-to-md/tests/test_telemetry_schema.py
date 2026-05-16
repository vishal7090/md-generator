from __future__ import annotations

from datetime import datetime
from pathlib import Path

from md_generator.core.schema.adapters.log_record import log_record_to_telemetry_event
from md_generator.core.schema.telemetry_event import TelemetryEvent
from md_generator.core.schema.validation import validate_telemetry_event
from md_generator.log.parser.models import LogRecord


def test_log_record_adapter() -> None:
    r = LogRecord(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        level="ERROR",
        logger="svc",
        thread=None,
        message="failed",
        raw_message="failed",
        stacktrace=None,
        source_file=Path("x.log"),
        line_number=3,
    )
    ev = log_record_to_telemetry_event(r)
    assert isinstance(ev, TelemetryEvent)
    assert not validate_telemetry_event(ev)
