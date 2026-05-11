from __future__ import annotations

from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.extractor import extract_to_markdown


def test_readme_stable_prefix(tmp_path: Path) -> None:
    """Golden-style check: key headings stay stable for RAG consumers."""
    fixture = Path(__file__).resolve().parent / "fixtures" / "sample.log"
    out = tmp_path / "g"
    from dataclasses import replace

    cfg = LogRunConfig()
    cfg = replace(
        cfg,
        input=replace(cfg.input, paths=[str(fixture)]),
        output=replace(cfg.output, path=str(out)),
    ).normalized()
    extract_to_markdown(cfg)
    text = (out / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# Log export\n")
    assert "## Overview" in text
    assert "## Artifact layout" in text
    levels = (out / "summary" / "levels.md").read_text(encoding="utf-8")
    assert "# Log levels" in levels
    assert "| ERROR |" in levels
