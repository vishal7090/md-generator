from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from md_generator.archive.extractors import (
    UnsupportedArchiveError,
    detect_archive_format,
    extract_archive,
    is_supported_archive_filename,
)

_LOG_SUFFIXES = {".log", ".txt", ".out", ".err"}


def _is_log_file(path: Path) -> bool:
    return path.suffix.lower() in _LOG_SUFFIXES or path.name.lower().endswith(".log")


def iter_log_files_from_dir(root: Path) -> Iterator[Path]:
    for p in sorted(root.rglob("*")):
        if p.is_file() and _is_log_file(p):
            yield p


@contextmanager
def extracted_archive_dir(archive: Path, *, cleanup: bool = True):
    fmt = detect_archive_format(archive)
    if fmt is None:
        raise UnsupportedArchiveError(f"Not a supported archive: {archive}")
    tmp = tempfile.mkdtemp(prefix="md-log-archive-")
    root = Path(tmp)
    jail = root.resolve()
    try:
        extract_archive(archive, root, jail, verbose=False)
        yield root
    finally:
        if cleanup:
            shutil.rmtree(tmp, ignore_errors=True)


def iter_log_files_from_archive(path: Path, *, cleanup: bool = True) -> Iterator[Path]:
    if not is_supported_archive_filename(path.name):
        if path.suffix.lower() == ".zip":
            pass
        elif detect_archive_format(path) is None:
            return
    with extracted_archive_dir(path, cleanup=cleanup) as root:
        yield from iter_log_files_from_dir(root)
