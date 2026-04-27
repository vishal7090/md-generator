from __future__ import annotations

from pathlib import Path


def find_tools_dir(name: str) -> Path | None:
    """Locate ``tools/<name>/`` by walking up from this package."""
    here = Path(__file__).resolve()
    for anc in here.parents:
        cand = anc / "tools" / name
        if cand.is_dir():
            return cand
    return None
