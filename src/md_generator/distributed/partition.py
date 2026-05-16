from __future__ import annotations

from pathlib import Path


def partition_paths(paths: list[Path], workers: int) -> list[list[Path]]:
    if workers <= 1 or len(paths) <= 1:
        return [paths]
    buckets: list[list[Path]] = [[] for _ in range(min(workers, len(paths)))]
    for i, p in enumerate(sorted(paths, key=lambda x: str(x))):
        buckets[i % len(buckets)].append(p)
    return [b for b in buckets if b]
