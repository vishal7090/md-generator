from __future__ import annotations

from abc import ABC, abstractmethod

from md_generator.graph.core.models import GraphMetadata, Node, Relationship


class BaseAdapter(ABC):
    """Graph source adapter."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection or load resources."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""

    def validate_connection(self) -> None:
        """Raise if unreachable; default is connect + noop."""
        self.connect()

    @abstractmethod
    def get_nodes(self) -> list[Node]:
        ...

    @abstractmethod
    def get_relationships(self) -> list[Relationship]:
        ...

    def get_subgraph(self, depth: int, start_node: str | None = None) -> GraphMetadata:
        """Bounded subgraph; default loads all nodes/rels then caller filters."""
        nodes = self.get_nodes()
        rels = self.get_relationships()
        return GraphMetadata(nodes=tuple(nodes), relationships=tuple(rels))
