from __future__ import annotations

from collections.abc import Iterator

from md_generator.core.artifacts.models import MarkdownArtifact
from md_generator.runtime.execution_context import ExecutionContext
from md_generator.runtime.metrics import stage_timer
from md_generator.sdk.stage_protocol import StageContext, TelemetryStage


def run_stages(
    stages: list[TelemetryStage],
    ctx: StageContext,
    exec_ctx: ExecutionContext | None = None,
) -> list[MarkdownArtifact]:
    ex = exec_ctx or ExecutionContext()
    artifacts: list[MarkdownArtifact] = []
    for stage in stages:
        if ex.cancelled:
            break
        with stage_timer(ex, stage.name):
            batch = list(stage.run(ctx))
            artifacts.extend(batch)
            ex.stage_counts[stage.name] = ex.stage_counts.get(stage.name, 0) + len(batch)
    return artifacts
