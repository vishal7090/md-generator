from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.embeddings.exporters.jsonl_exporter import export_jsonl


def export_chroma(path: Path, rows: Iterator[dict[str, object]]) -> int:
    # Embedding-ready JSONL sidecar; no vector generation.
    return export_jsonl(path.with_suffix(".jsonl"), rows)
