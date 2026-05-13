from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def export_parquet(path: Path, rows: Iterator[dict[str, object]]) -> int:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as e:
        raise ImportError("Install mdengine[log-export-parquet] for parquet export") from e
    batch = list(rows)
    if not batch:
        path.parent.mkdir(parents=True, exist_ok=True)
        return 0
    table = pa.Table.from_pylist(batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return len(batch)
