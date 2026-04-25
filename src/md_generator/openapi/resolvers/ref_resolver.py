from __future__ import annotations

from pathlib import Path
from typing import Any

from prance import ResolvingParser


def resolve_openapi_file(path: Path, *, strict: bool = True) -> dict[str, Any]:
    """Resolve ``$ref`` (and bundled references) into a single specification dict."""
    p = path.resolve()
    parser = ResolvingParser(str(p), strict=strict)
    spec = parser.specification
    if not isinstance(spec, dict):
        raise TypeError("Resolved OpenAPI specification must be a dict")
    return spec
