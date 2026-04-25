from __future__ import annotations

from typing import Any


def validate_openapi_version(doc: dict[str, Any]) -> str:
    v = doc.get("openapi") or doc.get("swagger")
    if not isinstance(v, str):
        raise ValueError("Missing openapi/swagger version field")
    if not v.startswith("3."):
        raise ValueError(f"Only OpenAPI 3.x is supported (got {v!r})")
    return v


def parse_openapi_dict(doc: dict[str, Any]) -> dict[str, Any]:
    """Light validation hook; returns the same dict for a stable pipeline surface."""
    validate_openapi_version(doc)
    return doc
