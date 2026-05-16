from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.ingestion.encoding_detector import decode_lines
from md_generator.log.ingestion.stream_reader import iter_text_lines


def iter_file_line_batches(
    path: Path,
    fallbacks: list[str],
    *,
    max_lines_per_batch: int,
    max_lines_total: int | None = None,
) -> Iterator[list[tuple[int, str]]]:
    """Yield bounded line batches without loading the full file."""
    raw = path.read_bytes()
    text = decode_lines(raw, fallbacks)
    batch: list[tuple[int, str]] = []
    total = 0
    for item in iter_text_lines(text, max_lines=max_lines_total):
        batch.append(item)
        total += 1
        if len(batch) >= max_lines_per_batch:
            yield batch
            batch = []
    if batch:
        yield batch


def iter_file_record_batches(
    path: Path,
    fallbacks: list[str],
    *,
    max_records: int,
    max_lines_total: int | None = None,
) -> Iterator[list[tuple[int, str]]]:
    """Alias for line batches (one parsed record per line in typical presets)."""
    yield from iter_file_line_batches(
        path,
        fallbacks,
        max_lines_per_batch=max_records,
        max_lines_total=max_lines_total,
    )
