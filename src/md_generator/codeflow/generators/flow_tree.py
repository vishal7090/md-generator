"""Static DFS expansion tree from a flow slice (for documentation, not runtime traces)."""

from __future__ import annotations

from typing import Any

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice


def flow_tree_to_serializable(entry_id: str, sl: FlowSlice, g: nx.DiGraph) -> dict[str, Any]:
    """Build a JSON-serializable tree by DFS on slice edges; repeated nodes allowed in different branches.

    ``back_edge`` is True when the target already appears on the current path (cycle / recursion hint).
    """
    adj: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for u, v, ed in sl.edges:
        adj.setdefault(u, []).append((v, dict(ed)))

    def dfs(node: str, path: list[str]) -> dict[str, Any]:
        in_path = node in path
        base: dict[str, Any] = {
            "id": node,
            "label": _node_short_label(g, node),
            "children": [],
        }
        if in_path:
            base["back_edge"] = True
            return base
        path_next = path + [node]
        for v, ed in adj.get(node, []):
            child = dfs(v, path_next)
            child["edge"] = {
                "condition": ed.get("condition"),
                "labels": ed.get("labels"),
            }
            base["children"].append(child)
        return base

    return {
        "entry_id": entry_id,
        "depth_limit": sl.depth,
        "truncated": sl.truncated,
        "tree": dfs(entry_id, []),
    }


def _node_short_label(g: nx.DiGraph, node: str) -> str:
    if node not in g:
        return node
    d = g.nodes[node]
    cls = d.get("class_name") or ""
    meth = d.get("method_name") or ""
    if cls and meth:
        return f"{cls}.{meth}"
    return str(node).split("::")[-1] if "::" in str(node) else str(node)
