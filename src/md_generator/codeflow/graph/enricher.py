"""Graph intelligence helpers (call subgraph + dependency reachability)."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.analysis import (
    called_by_direct_dependency,
    called_by_transitive_dependency,
    impact_descendants_dependency,
)
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges, iter_out_edges

_REL_CALLS = rel.REL_CALLS


def subgraph_by_relations(g: CodeflowGraph, relations: set[str]) -> CodeflowGraph:
    """Subgraph containing only edges whose ``relation`` is in ``relations``."""
    sg: CodeflowGraph = nx.MultiDiGraph()
    for n, d in g.nodes(data=True):
        sg.add_node(n, **dict(d))
    for u, v, _k, d in iter_multi_edges(g):
        r = d.get("relation", _REL_CALLS)
        if r in relations:
            sg.add_edge(u, v, **dict(d))
    return sg


def call_graph_view(g: CodeflowGraph) -> nx.DiGraph:
    """Simple digraph: one arc per (u,v) if any CALLS multiedge exists."""
    sg = nx.DiGraph()
    for u, v, _k, d in iter_multi_edges(g):
        if d.get("relation", _REL_CALLS) == _REL_CALLS:
            sg.add_edge(u, v)
    return sg


def called_by_direct(g: CodeflowGraph, node_id: str, cap: int) -> list[str]:
    return called_by_direct_dependency(g, node_id, cap)


def called_by_transitive(g: CodeflowGraph, node_id: str, cap: int) -> list[str]:
    return called_by_transitive_dependency(g, node_id, cap)


def structural_dependency_bullets(g: CodeflowGraph, entry_id: str, cap: int) -> list[str]:
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
            for _u, v, _k, ed in iter_out_edges(g, cid):
                r = ed.get("relation")
                if r in (rel.REL_INHERITS, rel.REL_IMPLEMENTS):
                    conf = float(ed.get("confidence", 1.0))
                    lines.append(f"- **{r}** → `{v}` (confidence {conf:.2f})")
    if fp:
        fid = f"file:{fp}"
        if g.has_node(fid):
            for _u, v, _k, ed in iter_out_edges(g, fid):
                if ed.get("relation") == rel.REL_IMPORTS:
                    conf = float(ed.get("confidence", 1.0))
                    lines.append(f"- **IMPORTS** → `{v}` (confidence {conf:.2f})")
    return lines[:cap]


def impact_descendants(g: CodeflowGraph, node_id: str, cap: int) -> list[str]:
    return impact_descendants_dependency(g, node_id, cap)
