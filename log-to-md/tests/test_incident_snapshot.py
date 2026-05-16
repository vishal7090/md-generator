from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.extractor import extract_to_markdown


def test_incident_markdown_snapshot(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "sample.log"
    out = tmp_path / "snap"
    cfg = LogRunConfig()
    cfg = replace(
        cfg,
        input=replace(cfg.input, paths=[str(fixture)]),
        output=replace(cfg.output, path=str(out)),
    ).normalized()
    extract_to_markdown(cfg)
    files = sorted((out / "incidents").glob("incident_*.md"))
    assert files
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("# Incident:")
    assert "## Summary" in text
    assert "## Representative Messages" in text
