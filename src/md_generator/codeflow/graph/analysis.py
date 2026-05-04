"""Dependency reachability for impact / reverse-impact (calls + structural relations, not containment)."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph import relations as rel

# CONTAINS models nesting (file/class/method), not operational dependency.
_SKIP_REACHABILITY: frozenset[str] = frozenset({rel.REL_CONTAINS})


def dependency_reachability_subgraph(g: nx.DiGraph) -> nx.DiGraph:
    """Directed subgraph for *impact* and *called-by*: all edges except ``CONTAINS``.

    Includes ``CALLS``, ``IMPORTS``, ``INHERITS``, ``IMPLEMENTS``, ``REFERENCES``,
    ``EVENT``, ``ASYNC`` (when emitted as its own relation), etc.
    """
    sg = nx.DiGraph()
    for n, d in g.nodes(data=True):
        sg.add_node(n, **dict(d))
    for u, v, d in g.edges(data=True):
        r = d.get("relation", rel.REL_CALLS)
        if r in _SKIP_REACHABILITY:
            continue
        sg.add_edge(u, v, **dict(d))
    return sg


def called_by_direct_dependency(g: nx.DiGraph, node_id: str, cap: int) -> list[str]:
    """Immediate predecessors in the dependency reachability graph."""
    dg = dependency_reachability_subgraph(g)
    if node_id not in dg:
        return []
    preds = sorted(dg.predecessors(node_id))
    return preds[:cap]


def called_by_transitive_dependency(g: nx.DiGraph, node_id: str, cap: int) -> list[str]:
    """``nx.ancestors`` in the dependency reachability graph (excluding ``node_id``)."""
    dg = dependency_reachability_subgraph(g)
    if node_id not in dg:
        return []
    anc = nx.ancestors(dg, node_id)
    anc.discard(node_id)
    return sorted(anc)[:cap]


def impact_descendants_dependency(g: nx.DiGraph, node_id: str, cap: int) -> list[str]:
    """``nx.descendants`` in the dependency reachability graph (excluding ``node_id``)."""
    dg = dependency_reachability_subgraph(g)
    if node_id not in dg:
        return []
    des = nx.descendants(dg, node_id)
    des.discard(node_id)
    return sorted(des)[:cap]
