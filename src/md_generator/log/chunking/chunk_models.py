from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SemanticChunk:
    chunk_id: str
    chunk_type: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)
