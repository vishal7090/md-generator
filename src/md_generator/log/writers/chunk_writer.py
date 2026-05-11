from __future__ import annotations

import json
from pathlib import Path

from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def write_rag_chunks(
    root: Path,
    records: list[LogRecord],
    *,
    records_per_chunk: int,
) -> None:
    if not records:
        return
    chunk_dir = root / "chunks"
    meta: list[dict[str, object]] = []
    for idx, start in enumerate(range(0, len(records), records_per_chunk), start=1):
        batch = records[start : start + records_per_chunk]
        lines = [
            f"<!-- chunk_id=log_chunk_{idx:04d} -->",
            f"# Log chunk {idx:04d}",
            "",
            f"_Records {start + 1}–{start + len(batch)} of {len(records)}_",
            "",
        ]
        for r in batch:
            ts = r.timestamp.isoformat() if r.timestamp else "n/a"
            lines.append(f"## {r.level} @ {ts}")
            lines.append("")
            lines.append(r.message[:4000])
            lines.append("")
        path = chunk_dir / f"chunk_{idx:04d}.md"
        write_text(path, "\n".join(lines))
        meta.append(
            {
                "chunk_id": f"log_chunk_{idx:04d}",
                "path": path.relative_to(root).as_posix(),
                "record_start": start + 1,
                "record_end": start + len(batch),
            },
        )
    write_text(
        root / "chunks" / "manifest.json",
        json.dumps(meta, indent=2) + "\n",
    )
