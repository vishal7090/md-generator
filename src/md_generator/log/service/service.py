from __future__ import annotations

from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.extractor import extract_to_markdown
from md_generator.log.core.zip_export import build_log_markdown_zip_bytes


def run_log_pipeline(cfg: LogRunConfig) -> Path:
    """Orchestration entry: run export and return output directory."""
    cfg = cfg.normalized()
    extract_to_markdown(cfg)
    return cfg.output_path()


def run_log_pipeline_zip(cfg: LogRunConfig) -> bytes:
    return build_log_markdown_zip_bytes(cfg)
