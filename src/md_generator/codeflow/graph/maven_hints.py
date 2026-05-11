"""Read ``groupId`` from a root ``pom.xml`` for cross-repo package hints (deterministic, no network)."""

from __future__ import annotations

import re
from pathlib import Path

_GROUP_RE = re.compile(
    r"<groupId>\s*([^<]+?)\s*</groupId>",
    re.I,
)


def maven_group_id(repo_root: Path) -> str | None:
    """Return first ``groupId`` text in ``pom.xml`` at repo root, if present."""
    pom = repo_root / "pom.xml"
    if not pom.is_file():
        return None
    try:
        text = pom.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _GROUP_RE.search(text)
    if not m:
        return None
    gid = m.group(1).strip()
    return gid or None


def maven_group_hints_for_roots(roots_with_labels: list[tuple[str, Path]]) -> dict[str, str]:
    """Map ``groupId`` string -> repo label (first wins; skip duplicates)."""
    out: dict[str, str] = {}
    for lab, root in roots_with_labels:
        gid = maven_group_id(root.resolve())
        if gid and gid not in out:
            out[gid] = lab
    return out
