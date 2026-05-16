from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from md_generator.core.artifacts.models import MarkdownArtifact


@dataclass(slots=True)
class StageContext:
    output_dir: Path
    config: Any
    records: list[Any] = field(default_factory=list)
    incidents: list[Any] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StageResult:
    artifacts: list[MarkdownArtifact] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class TelemetryStage(Protocol):
    name: str

    def run(self, ctx: StageContext) -> Iterator[MarkdownArtifact]: ...
