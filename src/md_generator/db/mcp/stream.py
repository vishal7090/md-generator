from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Iterator


def iter_zip_chunks(zip_path: Path, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            with zf.open(info) as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
