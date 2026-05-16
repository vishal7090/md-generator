from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path


def export_jsonl(path: Path, rows: Iterator[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
            n += 1
    return n
