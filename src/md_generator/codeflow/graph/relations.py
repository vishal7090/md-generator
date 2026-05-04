"""Canonical ``relation`` / edge ``kind`` strings for DiGraph edges and graph-schema export."""

from __future__ import annotations

REL_CALLS = "CALLS"
REL_IMPORTS = "IMPORTS"
REL_INHERITS = "INHERITS"
REL_IMPLEMENTS = "IMPLEMENTS"
REL_REFERENCES = "REFERENCES"
REL_EVENT = "EVENT"
REL_ASYNC = "ASYNC"
REL_CONTAINS = "CONTAINS"

EDGE_TYPES: tuple[str, ...] = (
    REL_CALLS,
    REL_IMPORTS,
    REL_INHERITS,
    REL_IMPLEMENTS,
    REL_REFERENCES,
    REL_EVENT,
    REL_ASYNC,
    REL_CONTAINS,
)

STRUCTURAL_RELATIONS: frozenset[str] = frozenset(
    {
        REL_IMPORTS,
        REL_INHERITS,
        REL_IMPLEMENTS,
        REL_REFERENCES,
        REL_EVENT,
        REL_ASYNC,
        REL_CONTAINS,
    }
)
