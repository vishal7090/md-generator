"""CFG container (language-agnostic; built only from IR)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CFGNode:
    id: str
    kind: str
    label: str
    method_name: str
    file_path: str
    line: int | None = None


@dataclass(slots=True)
class CFGEdge:
    source: str
    target: str
    label: str | None = None


@dataclass(slots=True)
class CFG:
    nodes: dict[str, CFGNode] = field(default_factory=dict)
    edges: list[CFGEdge] = field(default_factory=list)
    _next: int = field(default=0, repr=False)

    def new_id(self, prefix: str) -> str:
        self._next += 1
        return f"{prefix}_{self._next}"

    def add_node(self, *, prefix: str, kind: str, label: str, method_name: str, file_path: str, line: int | None) -> str:
        nid = self.new_id(prefix)
        self.nodes[nid] = CFGNode(
            id=nid,
            kind=kind,
            label=label[:200] if label else "",
            method_name=method_name,
            file_path=file_path,
            line=line,
        )
        return nid

    def add_edge(self, source: str, target: str, label: str | None = None) -> None:
        self.edges.append(CFGEdge(source=source, target=target, label=label))
