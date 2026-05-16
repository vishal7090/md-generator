from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.incremental.checkpoint import Checkpoint


def _file_inode(path: Path) -> int | None:
    try:
        return path.stat().st_ino
    except OSError:
        return None


def iter_new_lines(path: Path, checkpoint: Checkpoint | None) -> Iterator[tuple[int, str, int]]:
    """Yield (line_number, line, byte_offset) for bytes after checkpoint.offset."""
    start = 0 if checkpoint is None else max(0, checkpoint.offset)
    inode = _file_inode(path)
    if checkpoint and checkpoint.inode is not None and inode is not None and checkpoint.inode != inode:
        start = 0
    with path.open("rb") as fh:
        fh.seek(start)
        offset = start
        line_no = 0
        for raw in fh:
            try:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            except Exception:
                line = raw.decode("latin-1", errors="replace").rstrip("\r\n")
            line_no += 1
            yield line_no, line, offset
            offset += len(raw)


def checkpoint_after_read(path: Path, last_offset: int) -> Checkpoint:
    return Checkpoint(
        path=str(path.resolve()),
        offset=last_offset,
        inode=_file_inode(path),
    )
