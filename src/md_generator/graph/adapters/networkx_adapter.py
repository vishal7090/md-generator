from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx

from md_generator.graph.core.base_adapter import BaseAdapter
from md_generator.graph.core.models import Node, Relationship


def _labels_for_node(data: dict[str, Any] | None) -> tuple[str, ...]:
    if not data:
        return ("Node",)
    if "_labels" in data and isinstance(data["_labels"], (list, tuple)):
        return tuple(str(x) for x in data["_labels"])
    if "labels" in data and isinstance(data["labels"], (list, tuple)):
        return tuple(str(x) for x in data["labels"])
    if "labels" in data and isinstance(data["labels"], str) and data["labels"].strip():
        return (str(data["labels"]).strip(),)
    if "label" in data and data["label"] is not None and str(data["label"]).strip():
        return (str(data["label"]).strip(),)
    return ("Node",)


def _node_id_str(n: Any) -> str:
    return str(n)


def _rel_id_str(u: Any, v: Any, key: Any | None, idx: int, directed: bool) -> str:
    if key is None:
        return f"{u}->{v}::{idx}" if directed else f"{u}-{v}::{idx}"
    return f"{u}->{v}#{key}"


class NetworkXAdapter(BaseAdapter):
    """Adapter for in-memory NetworkX graphs or GraphML/GML files."""

    def __init__(self, graph: nx.Graph | nx.DiGraph | nx.MultiDiGraph | None = None, graph_file: Path | None = None) -> None:
        self._graph_file = Path(graph_file).expanduser() if graph_file else None
        self._graph = graph
        self._loaded: nx.Graph | nx.DiGraph | nx.MultiDiGraph | None = None

    def connect(self) -> None:
        if self._graph is not None:
            self._loaded = self._graph
            return
        if not self._graph_file or not self._graph_file.is_file():
            raise FileNotFoundError(f"graph_file not found: {self._graph_file}")
        suf = self._graph_file.suffix.lower()
        if suf == ".graphml":
            self._loaded = nx.read_graphml(self._graph_file)
        elif suf == ".gml":
            self._loaded = nx.read_gml(self._graph_file)
        else:
            raise ValueError(f"Unsupported graph file extension: {suf} (use .graphml or .gml)")

    def close(self) -> None:
        self._loaded = None

    def _g(self) -> nx.Graph | nx.DiGraph | nx.MultiDiGraph:
        if self._loaded is None:
            raise RuntimeError("adapter not connected")
        return self._loaded

    def get_nodes(self) -> list[Node]:
        g = self._g()
        out: list[Node] = []
        for nid, data in g.nodes(data=True):
            sid = _node_id_str(nid)
            props = {str(k): v for k, v in dict(data or {}).items() if k not in ("_labels", "labels", "label")}
            out.append(Node(id=sid, labels=_labels_for_node(dict(data or {})), properties=props))
        return out

    def get_relationships(self) -> list[Relationship]:
        g = self._g()
        out: list[Relationship] = []
        directed = g.is_directed()
        if isinstance(g, (nx.MultiDiGraph, nx.MultiGraph)):
            idx = 0
            for u, v, key, data in g.edges(keys=True, data=True):
                props = {str(k): val for k, val in dict(data or {}).items()}
                typ = str(props.pop("type", props.pop("label", "RELATED")))
                rid = _rel_id_str(u, v, key, idx, directed)
                if directed:
                    out.append(Relationship(id=rid, type=typ, start_node=_node_id_str(u), end_node=_node_id_str(v), properties=props))
                else:
                    su, sv = _node_id_str(u), _node_id_str(v)
                    a, b = (su, sv) if su <= sv else (sv, su)
                    out.append(Relationship(id=rid, type=typ, start_node=a, end_node=b, properties=props))
                idx += 1
            return out
        idx = 0
        for u, v, data in g.edges(data=True):
            props = {str(k): val for k, val in dict(data or {}).items()}
            typ = str(props.pop("type", props.pop("label", "RELATED")))
            rid = _rel_id_str(u, v, None, idx, directed)
            if directed:
                out.append(Relationship(id=rid, type=typ, start_node=_node_id_str(u), end_node=_node_id_str(v), properties=props))
            else:
                su, sv = _node_id_str(u), _node_id_str(v)
                a, b = (su, sv) if su <= sv else (sv, su)
                out.append(Relationship(id=rid, type=typ, start_node=a, end_node=b, properties=props))
            idx += 1
        return out
