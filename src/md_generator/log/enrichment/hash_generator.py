from __future__ import annotations

import hashlib


def stable_hash(text: str, *, n: int = 16) -> str:
    h = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return h[:n]
