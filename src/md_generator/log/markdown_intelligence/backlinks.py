from __future__ import annotations

from typing import Any


def build_backlink_index(artifacts: list[Any]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for art in artifacts:
        aid = getattr(art, "artifact_id", None) or art.get("artifact_id")
        if not aid:
            continue
        md = getattr(art, "metadata", None) or art.get("metadata", {})
        svc = getattr(md, "service", None) if md else None
        if svc is None and isinstance(md, dict):
            svc = md.get("service")
        keys = [str(svc)] if svc else []
        tags = getattr(md, "tags", None) if md else None
        if tags:
            keys.extend(str(t) for t in tags)
        for k in keys:
            if not k:
                continue
            index.setdefault(k, []).append(str(aid))
    for k in index:
        index[k] = sorted(set(index[k]))
    return index
