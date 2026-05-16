from __future__ import annotations

from typing import Any

REQUIRED_ARTIFACT_KEYS = frozenset({"artifact_id", "artifact_type", "title", "content"})
ALLOWED_FRONTMATTER_KEYS = frozenset(
    {
        "artifact_type",
        "artifact_id",
        "severity",
        "service",
        "chunk_id",
        "tags",
        "agent_hints",
        "lineage",
    },
)


def validate_artifact_dict(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_ARTIFACT_KEYS - set(data.keys())
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")
    aid = data.get("artifact_id")
    if aid is not None and not str(aid).strip():
        errors.append("artifact_id must be non-empty")
    return errors


def validate_frontmatter_keys(keys: set[str]) -> list[str]:
    unknown = keys - ALLOWED_FRONTMATTER_KEYS
    if unknown:
        return [f"unknown frontmatter keys: {sorted(unknown)}"]
    return []
