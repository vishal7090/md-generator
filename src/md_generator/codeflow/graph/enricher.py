"""Graph intelligence helpers (call-only subgraph; backward compatible)."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph import relations as rel

_REL_CALLS = rel.REL_CALLS


def subgraph_by_relations(g: nx.DiGraph, relations: set[str]) -> nx.DiGraph:
    """Directed subgraph containing only edges whose ``relation`` is in ``relations``."""
    sg = nx.DiGraph()
    for n, d in g.nodes(data=True):
        sg.add_node(n, **dict(d))
    for u, v, d in g.edges(data=True):
        r = d.get("relation", _REL_CALLS)
        if r in relations:
            sg.add_edge(u, v, **d)
    return sg


def call_graph_view(g: nx.DiGraph) -> nx.DiGraph:
    """Subgraph keeping only semantic CALLS edges (default relation on call edges)."""
    sg = nx.DiGraph()
    for u, v, d in g.edges(data=True):
        rel = d.get("relation", _REL_CALLS)
        if rel == _REL_CALLS:
            sg.add_edge(u, v)
    return sg


def called_by_direct(g: nx.DiGraph, node_id: str, cap: int) -> list[str]:
    """Direct callers (predecessors in call graph), sorted, capped."""
    cg = call_graph_view(g)
    if node_id not in cg:
        return []
    preds = sorted(cg.predecessors(node_id))
    return list(preds)[:cap]


def called_by_transitive(g: nx.DiGraph, node_id: str, cap: int) -> list[str]:
    """Transitive callers (``nx.ancestors`` on call-only view), sorted, capped."""
    cg = call_graph_view(g)
    if node_id not in cg:
        return []
    anc = nx.ancestors(cg, node_id)
    anc.discard(node_id)
    out = sorted(anc)
    return out[:cap]


def structural_dependency_bullets(g: nx.DiGraph, entry_id: str, cap: int) -> list[str]:
    """Human-readable structural edges (IMPORT / INHERITS / IMPLEMENTS) for the entry's file/class."""
    if entry_id not in g:
        return []
    d = g.nodes[entry_id]
    fp = (d.get("file_path") or "").strip()
    cn = d.get("class_name")
    lines: list[str] = []
    if fp and cn:
        cid = f"class:{fp}::{cn}"
        if g.has_node(cid):
            for _u, v, ed in g.out_edges(cid, data=True):
                r = ed.get("relation")
                if r in (rel.REL_INHERITS, rel.REL_IMPLEMENTS):
                    conf = float(ed.get("confidence", 1.0))
                    lines.append(f"- **{r}** → `{v}` (confidence {conf:.2f})")
    if fp:
        fid = f"file:{fp}"
        if g.has_node(fid):
            for _u, v, ed in g.out_edges(fid, data=True):
                if ed.get("relation") == rel.REL_IMPORTS:
                    conf = float(ed.get("confidence", 1.0))
                    lines.append(f"- **IMPORTS** → `{v}` (confidence {conf:.2f})")
    return lines[:cap]


def impact_descendants(g: nx.DiGraph, node_id: str, cap: int) -> list[str]:
    """Transitive callees from ``node_id`` in the call graph, sorted, capped."""
    cg = call_graph_view(g)
    if node_id not in cg:
        return []
    des = sorted(nx.descendants(cg, node_id))
    return list(des)[:cap]
