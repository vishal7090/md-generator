from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.chunking.chunk_models import SemanticChunk
from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.embeddings.exporters.chroma_exporter import export_chroma
from md_generator.log.embeddings.exporters.faiss_exporter import export_faiss
from md_generator.log.embeddings.exporters.jsonl_exporter import export_jsonl
from md_generator.log.embeddings.exporters.parquet_exporter import export_parquet


def _rows(chunks: Iterator[SemanticChunk]) -> Iterator[dict[str, object]]:
    for ch in chunks:
        yield {"chunk_id": ch.chunk_id, "text": ch.content, "metadata": ch.metadata}


def export_embeddings(out_root: Path, chunks: list[SemanticChunk], cfg: LogRunConfig) -> dict[str, int]:
    dest = out_root / cfg.embeddings.output_subdir
    dest.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    it = iter(chunks)
    for name in cfg.embeddings.exporters:
        key = name.lower().strip()
        if key == "jsonl":
            counts["jsonl"] = export_jsonl(dest / "chunks.jsonl", _rows(it))
            it = iter(chunks)
        elif key == "parquet":
            counts["parquet"] = export_parquet(dest / "chunks.parquet", _rows(it))
            it = iter(chunks)
        elif key == "chroma":
            counts["chroma"] = export_chroma(dest / "chroma", _rows(it))
            it = iter(chunks)
        elif key == "faiss":
            counts["faiss"] = export_faiss(dest / "faiss", _rows(it))
            it = iter(chunks)
    return counts
