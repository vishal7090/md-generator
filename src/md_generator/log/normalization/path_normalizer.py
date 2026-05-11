from __future__ import annotations

import re

# Windows and POSIX-ish paths (heuristic)
_PATH = re.compile(
    r"(?:[A-Za-z]:\\[^\s]+|/[^\s]+/[^\s]+)",
)


def mask_paths(text: str) -> str:
    return _PATH.sub("<PATH>", text)
