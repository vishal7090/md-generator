from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionContext:
    cancelled: bool = False
    stage_timings_ms: dict[str, int] = field(default_factory=dict)
    stage_counts: dict[str, int] = field(default_factory=dict)
    checkpoint_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
