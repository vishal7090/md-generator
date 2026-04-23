from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Node:
    id: str
    labels: tuple[str, ...]
    properties: dict[str, Any]

    def labels_sorted(self) -> tuple[str, ...]:
        return tuple(sorted(self.labels))


@dataclass(frozen=True)
class Relationship:
    id: str
    type: str
    start_node: str
    end_node: str
    properties: dict[str, Any]


@dataclass
class GraphMetadata:
    nodes: tuple[Node, ...] = field(default_factory=tuple)
    relationships: tuple[Relationship, ...] = field(default_factory=tuple)
