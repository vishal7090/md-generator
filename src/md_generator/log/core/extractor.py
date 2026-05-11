from __future__ import annotations

from datetime import datetime, timezone

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.pipeline import run_pipeline
from md_generator.log.parser.models import RunContext


def extract_to_markdown(cfg: LogRunConfig) -> None:
    cfg = cfg.normalized()
    ctx = RunContext(
        input_paths=cfg.resolved_input_paths(),
        output_dir=cfg.output_path(),
        config=cfg,
        started_at=datetime.now(timezone.utc),
        records=[],
        parse_result=None,
    )
    run_pipeline(ctx)
