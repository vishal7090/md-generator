from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OtelSpan:
    trace_id: str
    span_id: str
    name: str
    service: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OtelLogRecord:
    body: str
    severity: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
