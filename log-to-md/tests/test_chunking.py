from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from md_generator.log.chunking.chunk_engine import iter_semantic_chunks
from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.incidents.incident_engine import build_incidents
from md_generator.log.parser.models import LogRecord


def test_semantic_chunk_ids(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "sample.log"
    from md_generator.log.core.extractor import extract_to_markdown

    out = tmp_path / "out"
    cfg = LogRunConfig()
    cfg = replace(
        cfg,
        input=replace(cfg.input, paths=[str(fixture)]),
        output=replace(cfg.output, path=str(out), generate_chunks=True),
        chunking=replace(cfg.chunking, enabled=True, strategies=["incident", "timeline"]),
    ).normalized()
    extract_to_markdown(cfg)
    manifest = out / "chunks" / "manifest.json"
    assert manifest.is_file()
