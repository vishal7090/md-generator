from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def merge_record_shards(shards: list[Path]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for shard in sorted(shards):
        if not shard.is_file():
            continue
        for line in shard.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                merged.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return merged
