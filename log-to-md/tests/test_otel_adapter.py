from __future__ import annotations

from md_generator.core.schema.adapters.otel import otel_log_to_event, otel_span_to_event
from md_generator.core.schema.validation import validate_telemetry_event
from md_generator.otel.otel_models import OtelLogRecord, OtelSpan


def test_otel_adapters_to_telemetry_event() -> None:
    log_ev = otel_log_to_event(OtelLogRecord(body="timeout", severity="ERROR"))
    span_ev = otel_span_to_event(
        OtelSpan(trace_id="abc", span_id="def", name="GET /", service="api"),
    )
    assert not validate_telemetry_event(log_ev)
    assert not validate_telemetry_event(span_ev)
    assert span_ev.signal_type == "trace"
