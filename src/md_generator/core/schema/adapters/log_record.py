from __future__ import annotations

from md_generator.core.schema.telemetry_event import TelemetryEvent
from md_generator.log.parser.models import LogRecord


def log_record_to_telemetry_event(record: LogRecord) -> TelemetryEvent:
    attrs = dict(record.metadata)
    attrs["logger"] = record.logger
    attrs["thread"] = record.thread
    attrs["line_number"] = record.line_number
    attrs["source_file"] = str(record.source_file)
    if record.correlation_id:
        attrs["correlation_id"] = record.correlation_id
    if record.fingerprint:
        attrs["fingerprint"] = record.fingerprint
    return TelemetryEvent(
        timestamp=record.timestamp,
        source=str(record.source_file),
        signal_type="log",
        severity=record.level,
        message=record.message,
        attributes=attrs,
    )
