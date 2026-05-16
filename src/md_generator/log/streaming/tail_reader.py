from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path


def iter_tail_lines(path: Path, *, poll_seconds: float = 0.5, start_at_end: bool = False) -> Iterator[str]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        if start_at_end:
            fh.seek(0, 2)
        while True:
            line = fh.readline()
            if line:
                yield line.rstrip("\r\n")
            else:
                time.sleep(poll_seconds)
