from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.core.errors import EncodingError
from md_generator.log.ingestion.encoding_detector import decode_lines


def iter_text_lines(
    text: str,
    *,
    max_lines: int | None,
) -> Iterator[tuple[int, str]]:
    n = 0
    for i, line in enumerate(text.splitlines(), start=1):
        yield i, line
        n += 1
        if max_lines is not None and n >= max_lines:
            break


def read_file_as_text(path: Path, fallbacks: list[str], max_lines: int | None = None) -> tuple[str, int]:
    """Return full text (possibly truncated by line count) and line count read."""
    raw = path.read_bytes()
    try:
        text = decode_lines(raw, fallbacks)
    except EncodingError:
        raise
    if max_lines is None:
        lines = text.splitlines()
        return text, len(lines)
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines), len(lines)
    return "\n".join(lines[:max_lines]), max_lines
