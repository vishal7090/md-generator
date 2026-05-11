from __future__ import annotations

from dataclasses import dataclass, field

from md_generator.log.aggregation.metrics import RunMetrics


@dataclass
class ExecutionContext:
    metrics: RunMetrics = field(default_factory=RunMetrics)
