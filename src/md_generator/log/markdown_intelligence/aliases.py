from __future__ import annotations

import re


def slugify_service(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "unknown"


def build_alias_map(services: list[str]) -> dict[str, str]:
    return {slugify_service(s): s for s in services if s}
