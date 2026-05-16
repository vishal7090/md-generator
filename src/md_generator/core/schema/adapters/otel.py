from __future__ import annotations

from md_generator.core.schema.telemetry_event import TelemetryEvent
from md_generator.otel.otel_models import OtelLogRecord, OtelSpan


def otel_log_to_event(rec: OtelLogRecord, *, source: str = "otel") -> TelemetryEvent:
    return TelemetryEvent(
        timestamp=None,
        source=source,
        signal_type="log",
        severity=rec.severity or "INFO",
        message=rec.body,
        attributes=dict(rec.attributes),
    )


def otel_span_to_event(span: OtelSpan, *, source: str = "otel") -> TelemetryEvent:
    return TelemetryEvent(
        timestamp=None,
        source=source,
        signal_type="trace",
        severity="INFO",
        message=span.name,
        attributes={
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "service": span.service,
            **span.attributes,
        },
    )
