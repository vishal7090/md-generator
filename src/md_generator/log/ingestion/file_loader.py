from __future__ import annotations

from pathlib import Path


def expand_log_paths(paths: list[Path]) -> list[Path]:
    """Expand directories to *.log and *.txt; keep files as-is."""
    out: list[Path] = []
    for p in paths:
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(p.glob("**/*.log")))
            out.extend(sorted(p.glob("**/*.txt")))
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[Path] = []
    for x in out:
        k = str(x.resolve())
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq
