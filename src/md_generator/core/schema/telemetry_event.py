from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TelemetryEvent:
    timestamp: datetime | None
    source: str
    signal_type: str
    severity: str
    message: str
    attributes: dict[str, Any] = field(default_factory=dict)
