"""Enrich serialized graph JSON for Cytoscape (layers, preset positions, compound clusters)."""

from __future__ import annotations

import re
from collections import defaultdict

import networkx as nx


def _cluster_key(node: dict) -> str:
    fp = (node.get("file_path") or "").strip().replace("\\", "/")
    if not fp:
        return "unscoped"
    parts = fp.rsplit("/", 1)
    return parts[0] if len(parts) > 1 else "root"


def _safe_cluster_id(cluster_key: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", cluster_key)[:80].strip("_") or "grp"
    return f"__grp__{s}"


def enrich_graph_for_views(graph: dict, entry_id: str) -> dict:
    """Return a copy of ``graph`` with ``cy_depth``, preset positions, and compound parent metadata.

    Does not mutate the original dict (safe for JSON already written to disk).
    """
    nodes_in = list(graph.get("nodes") or [])
    edges_in = list(graph.get("edges") or [])
    G = nx.MultiDiGraph()
    for n in nodes_in:
        nid = n.get("id")
        if nid:
            G.add_node(nid)
    for i, e in enumerate(edges_in):
        u, v = e.get("source"), e.get("target")
        if u and v and G.has_node(u) and G.has_node(v):
            ek = e.get("key")
            if ek is None:
                ek = i
            G.add_edge(u, v, key=ek)

    if entry_id in G:
        lengths: dict[str, int] = dict(nx.single_source_shortest_path_length(G, entry_id))
    else:
        lengths = {n: 0 for n in G.nodes()}

    rank_bucket: dict[int, list[str]] = defaultdict(list)
    for nid in G.nodes():
        rank_bucket[lengths.get(nid, 0)].append(nid)

    rank_positions: dict[str, tuple[float, float]] = {}
    for r in sorted(rank_bucket.keys()):
        ids = sorted(rank_bucket[r])
        for i, nid in enumerate(ids):
            rank_positions[nid] = (float(r) * 280.0, float(i) * 88.0)

    cluster_keys: dict[str, str] = {}
    for n in nodes_in:
        nid = n.get("id")
        if not nid:
            continue
        ck = _cluster_key(n)
        cluster_keys.setdefault(ck, _safe_cluster_id(ck))

    compound_parents = [{"id": cluster_keys[ck], "label": ck} for ck in sorted(cluster_keys.keys())]

    nodes_out: list[dict] = []
    for n in nodes_in:
        nid = n.get("id")
        if not nid:
            continue
        row = {**n}
        row["cy_depth"] = int(lengths.get(nid, 0))
        px, py = rank_positions.get(nid, (0.0, 0.0))
        row["cy_preset_x"] = px
        row["cy_preset_y"] = py
        ck = _cluster_key(n)
        row["cy_cluster_id"] = cluster_keys[ck]
        row["cy_label_short"] = _short_label(n, nid)
        nodes_out.append(row)

    return {
        "nodes": nodes_out,
        "edges": edges_in,
        "entry_id": entry_id,
        "compound_parents": compound_parents,
    }


def _short_label(node: dict, nid: str) -> str:
    cn = node.get("class_name")
    mn = node.get("method_name")
    if cn and mn:
        return f"{cn}.{mn}"
    if mn:
        return str(mn)
    tail = nid.split("::", 1)[-1] if "::" in nid else nid
    return tail if len(tail) < 48 else tail[:45] + "…"
