"""MultiDiGraph helpers: edge payloads, collapse views, unique-neighbor semantics."""

from __future__ import annotations

from typing import Any, Iterator

import networkx as nx

from md_generator.codeflow.graph import relations as rel

# Runtime graphs from ``build_graph`` are ``MultiDiGraph``; helpers also accept plain ``DiGraph`` (tests, subgraph copies).
CodeflowGraph = nx.MultiDiGraph | nx.DiGraph

_SKIP_REACHABILITY: frozenset[str] = frozenset({rel.REL_CONTAINS})


def edge_payload(
    *,
    relation: str,
    condition: str | None = None,
    confidence: float = 1.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Standard edge attributes: ``relation`` + mirrored ``kind`` for query/export."""
    d: dict[str, Any] = {
        "relation": relation,
        "kind": relation,
        "condition": condition,
        "confidence": float(confidence),
    }
    d.update(kwargs)
    return d


def iter_multi_edges(g: nx.Graph) -> Iterator[tuple[Any, Any, Any, dict[str, Any]]]:
    if g.is_multigraph():
        yield from g.edges(keys=True, data=True)
    else:
        for u, v, d in g.edges(data=True):
            yield u, v, None, d


def edge_data_dicts(g: nx.Graph, u: Any, v: Any) -> list[dict[str, Any]]:
    """Attribute dicts for all edges ``u → v`` (one entry for simple digraphs)."""
    if not g.has_edge(u, v):
        return []
    if g.is_multigraph():
        return [dict(d) for d in g[u][v].values()]
    return [dict(g.edges[u, v])]


def iter_out_edges(g: nx.Graph, n: Any) -> Iterator[tuple[Any, Any, Any, dict[str, Any]]]:
    if g.is_multigraph():
        yield from g.out_edges(n, keys=True, data=True)
    else:
        for _u, v, d in g.out_edges(n, data=True):
            yield n, v, None, d


def call_collapsed_digraph(g: nx.Graph) -> nx.DiGraph:
    """Single CALLS hop per (u,v) for shortest-path layering / flow slice."""
    cg = nx.DiGraph()
    cg.add_nodes_from(g.nodes(data=True))
    for u, v, _k, d in iter_multi_edges(g):
        if d.get("relation", rel.REL_CALLS) != rel.REL_CALLS:
            continue
        cg.add_edge(u, v)
    return cg


def collapse_for_reachability(g: nx.Graph) -> nx.DiGraph:
    """Directed simple graph: one arc per (u,v) if any non-CONTAINS edge exists."""
    sg = nx.DiGraph()
    sg.add_nodes_from(g.nodes())
    for u, v, _k, d in iter_multi_edges(g):
        r = d.get("relation", rel.REL_CALLS)
        if r in _SKIP_REACHABILITY:
            continue
        sg.add_edge(u, v)
    return sg


def find_edge_key_with_relation(g: nx.Graph, u: Any, v: Any, relation: str) -> Any | None:
    if not g.has_edge(u, v):
        return None
    if g.is_multigraph():
        for k, d in g[u][v].items():
            if d.get("relation") == relation:
                return k
        return None
    d = g.edges[u, v]
    return 0 if d.get("relation") == relation else None


def unique_predecessor_count(g: nx.Graph, n: Any) -> int:
    return len(list(g.predecessors(n)))


def unique_successor_count(g: nx.Graph, n: Any) -> int:
    return len(list(g.successors(n)))
