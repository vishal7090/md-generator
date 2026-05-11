from __future__ import annotations

# Logger name usually comes from regex group; placeholder for future heuristics.


def refine_logger(name: str | None) -> str | None:
    if name is None:
        return None
    s = str(name).strip()
    return s or None
