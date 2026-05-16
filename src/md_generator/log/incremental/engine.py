from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from md_generator.log.incremental.checkpoint import Checkpoint, load_checkpoint, save_checkpoint
from md_generator.log.incremental.resume_reader import checkpoint_after_read, iter_new_lines


def process_incremental(
    path: Path,
    checkpoint_path: Path,
    line_handler: Callable[[list[tuple[int, str]]], None],
    *,
    batch_size: int = 500,
) -> Checkpoint:
    cp = load_checkpoint(checkpoint_path)
    batch: list[tuple[int, str]] = []
    last_offset = cp.offset if cp else 0
    try:
        for line_no, line, offset in iter_new_lines(path, cp):
            batch.append((line_no, line))
            last_offset = offset + len(line.encode("utf-8", errors="replace")) + 1
            if len(batch) >= batch_size:
                line_handler(batch)
                batch = []
        if batch:
            line_handler(batch)
    except Exception:
        save_checkpoint(checkpoint_path, Checkpoint(path=str(path), offset=0))
        raise
    new_cp = checkpoint_after_read(path, last_offset)
    save_checkpoint(checkpoint_path, new_cp)
    return new_cp
