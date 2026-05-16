from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GraphNode:
    node_id: str
    label: str
    kind: str


@dataclass(slots=True)
class GraphEdge:
    source_id: str
    target_id: str
    relation: str
