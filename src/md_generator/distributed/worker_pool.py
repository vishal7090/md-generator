from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable


def _shard_worker(args: tuple[str, list[str]]) -> str:
    shard_path, file_strs = args
    out: list[dict[str, Any]] = []
    for fs in file_strs:
        p = Path(fs)
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), start=1):
                out.append({"source": str(p), "line": i, "message": line[:2000]})
        except OSError:
            continue
    Path(shard_path).write_text("\n".join(json.dumps(r) for r in out), encoding="utf-8")
    return shard_path


def process_files_distributed(
    paths: list[Path],
    staging: Path,
    workers: int,
) -> list[Path]:
    staging.mkdir(parents=True, exist_ok=True)
    from md_generator.distributed.partition import partition_paths

    buckets = partition_paths(paths, workers)
    tasks = [
        (str(staging / f"shard_{i}.jsonl"), [str(p) for p in bucket])
        for i, bucket in enumerate(buckets)
    ]
    shards: list[Path] = []
    with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
        for shard in pool.map(_shard_worker, tasks):
            shards.append(Path(shard))
    return shards
