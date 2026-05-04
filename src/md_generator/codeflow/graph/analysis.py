"""Dependency reachability and multi-edge helpers (``MultiDiGraph``)."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges, iter_out_edges

_SKIP_REACHABILITY: frozenset[str] = frozenset({rel.REL_CONTAINS})


def dependency_reachability_subgraph(g: CodeflowGraph) -> nx.DiGraph:
    """Collapse to a simple digraph: non-CONTAINS edges (one arc per pair)."""
    sg = nx.DiGraph()
    sg.add_nodes_from(g.nodes())
    for u, v, _k, d in iter_multi_edges(g):
        r = d.get("relation", rel.REL_CALLS)
        if r in _SKIP_REACHABILITY:
            continue
        sg.add_edge(u, v)
    return sg


def edges_by_kind(g: CodeflowGraph, kind: str) -> list[tuple[str, str, dict[str, object]]]:
    out: list[tuple[str, str, dict[str, object]]] = []
    for u, v, _k, d in iter_multi_edges(g):
        r = d.get("relation") or d.get("kind")
        if r == kind:
            out.append((u, v, dict(d)))
    return out


def event_flow_edges(g: CodeflowGraph) -> list[tuple[str, str, dict[str, object]]]:
    return edges_by_kind(g, rel.REL_EVENT)


def references_from(g: CodeflowGraph, node_id: str) -> list[str]:
    out: list[str] = []
    if node_id not in g:
        return out
    for _u, v, _k, d in iter_out_edges(g, node_id):
        if d.get("relation") == rel.REL_REFERENCES or d.get("kind") == rel.REL_REFERENCES:
            out.append(v)
    return out


def called_by_direct_dependency(g: CodeflowGraph, node_id: str, cap: int) -> list[str]:
    dg = dependency_reachability_subgraph(g)
    if node_id not in dg:
        return []
    preds = sorted(dg.predecessors(node_id))
    return preds[:cap]


def called_by_transitive_dependency(g: CodeflowGraph, node_id: str, cap: int) -> list[str]:
    dg = dependency_reachability_subgraph(g)
    if node_id not in dg:
        return []
    anc = nx.ancestors(dg, node_id)
    anc.discard(node_id)
    return sorted(anc)[:cap]


def impact_descendants_dependency(g: CodeflowGraph, node_id: str, cap: int) -> list[str]:
    dg = dependency_reachability_subgraph(g)
    if node_id not in dg:
        return []
    des = nx.descendants(dg, node_id)
    des.discard(node_id)
    return sorted(des)[:cap]
