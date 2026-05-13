from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from md_generator.log.chunking.chunk_engine import iter_semantic_chunks
from md_generator.log.chunking.chunk_models import SemanticChunk
from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.incidents.models import Incident
from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def write_semantic_chunks(
    root: Path,
    records: list[LogRecord],
    incidents: list[Incident],
    cfg: LogRunConfig,
) -> list[SemanticChunk]:
    chunks = list(iter_semantic_chunks(records, incidents, cfg))
    if not chunks and cfg.chunk.enabled:
        # legacy fixed-size fallback
        from md_generator.log.writers.chunk_writer import write_rag_chunks

        write_rag_chunks(root, records, records_per_chunk=cfg.chunk.records_per_md_chunk)
        return []
    meta: list[dict[str, object]] = []
    for i, ch in enumerate(chunks, start=1):
        fname = f"chunk_{i:04d}.md"
        body = [
            f"<!-- chunk_id={ch.chunk_id} -->",
            f"# {ch.title}",
            "",
            ch.content,
            "",
        ]
        path = root / "chunks" / fname
        write_text(path, "\n".join(body))
        meta.append(
            {
                "chunk_id": ch.chunk_id,
                "chunk_type": ch.chunk_type,
                "path": path.relative_to(root).as_posix(),
                "metadata": ch.metadata,
                "source_refs": ch.source_refs,
            },
        )
    if meta:
        write_text(root / "chunks" / "manifest.json", json.dumps(meta, indent=2) + "\n")
    return chunks


def iter_chunk_export_records(chunks: Iterator[SemanticChunk]) -> Iterator[dict[str, object]]:
    for ch in chunks:
        yield {"chunk_id": ch.chunk_id, "text": ch.content, "metadata": ch.metadata}
