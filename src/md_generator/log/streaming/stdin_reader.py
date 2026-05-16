from __future__ import annotations

import sys
from collections.abc import Iterator


def iter_stdin_lines() -> Iterator[str]:
    for line in sys.stdin:
        yield line.rstrip("\r\n")
