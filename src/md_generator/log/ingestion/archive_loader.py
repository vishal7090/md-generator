from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path


def iter_zip_log_members(zip_path: Path) -> Iterator[tuple[str, bytes]]:
    """Yield (member_name, raw_bytes) for .log/.txt inside a ZIP."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.lower()
            if not (name.endswith(".log") or name.endswith(".txt")):
                continue
            with zf.open(info) as fh:
                yield info.filename, fh.read()


def sniff_zip(path: Path) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False
