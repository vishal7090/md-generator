from __future__ import annotations

from md_generator.core.schema.telemetry_event import TelemetryEvent

ALLOWED_SIGNAL_TYPES = frozenset({"log", "trace", "metric", "event"})


def validate_telemetry_event(ev: TelemetryEvent) -> list[str]:
    errors: list[str] = []
    if not ev.source.strip():
        errors.append("source must be non-empty")
    if ev.signal_type not in ALLOWED_SIGNAL_TYPES:
        errors.append(f"signal_type must be one of {sorted(ALLOWED_SIGNAL_TYPES)}")
    if not ev.message and ev.signal_type == "log":
        errors.append("log events require message")
    return errors
