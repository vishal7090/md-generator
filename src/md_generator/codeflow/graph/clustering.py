"""Graph clustering: file imports, structural (CALLS+IMPORTS), optional semantic/hybrid."""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges as _iter_edges

_LOG = logging.getLogger(__name__)


def file_import_digraph(g: CodeflowGraph) -> nx.DiGraph:
    """Subgraph of ``file:`` nodes linked by ``IMPORTS`` edges only."""
    fg = nx.DiGraph()
    for n in g.nodes():
        if isinstance(n, str) and n.startswith("file:"):
            fg.add_node(n, **dict(g.nodes[n]))
    for u, v, _k, d in _iter_edges(g):
        if d.get("relation") != rel.REL_IMPORTS:
            continue
        if isinstance(u, str) and u.startswith("file:") and isinstance(v, str) and v.startswith("file:"):
            if not fg.has_edge(u, v):
                fg.add_edge(u, v)
    return fg


def greedy_modularity_file_communities(
    g: CodeflowGraph,
    *,
    max_undirected_nodes: int = 4000,
) -> list[list[str]]:
    """Run ``greedy_modularity_communities`` on an undirected view of the file import graph."""
    fg = file_import_digraph(g)
    if fg.number_of_nodes() == 0:
        return []
    ug = nx.Graph()
    ug.add_nodes_from(fg.nodes())
    for u, v in fg.edges():
        ug.add_edge(u, v)
    if ug.number_of_nodes() > max_undirected_nodes:
        ranked = sorted(ug.nodes(), key=lambda n: ug.degree(n), reverse=True)
        keep = set(ranked[:max_undirected_nodes])
        ug = ug.subgraph(keep).copy()
    comms = nx.community.greedy_modularity_communities(ug)
    return [sorted(c) for c in comms]


def greedy_modularity_structural_communities(
    g: CodeflowGraph,
    *,
    max_undirected_nodes: int = 4000,
) -> list[list[str]]:
    """Modularity on undirected graph from CALLS + IMPORTS edges (node set = all endpoints)."""
    ug = nx.Graph()
    rels = {rel.REL_CALLS, rel.REL_IMPORTS}
    for u, v, _k, d in _iter_edges(g):
        if d.get("relation") not in rels:
            continue
        ug.add_node(u)
        ug.add_node(v)
        ug.add_edge(u, v)
    if ug.number_of_nodes() == 0:
        return []
    if ug.number_of_nodes() > max_undirected_nodes:
        ranked = sorted(ug.nodes(), key=lambda n: ug.degree(n), reverse=True)
        keep = set(ranked[:max_undirected_nodes])
        ug = ug.subgraph(keep).copy()
    comms = nx.community.greedy_modularity_communities(ug)
    return [sorted(c) for c in comms]


def semantic_clusters_from_embeddings(embeddings: list[list[float]], k: int = 8) -> list[int]:
    """Optional KMeans labels; requires ``scikit-learn``. Raises ``ImportError`` if missing."""
    try:
        from sklearn.cluster import KMeans
    except ImportError as e:
        raise ImportError("semantic clustering requires scikit-learn (optional dependency)") from e
    import numpy as np

    arr = np.array(embeddings, dtype=np.float64)
    if arr.size == 0:
        return []
    km = KMeans(n_clusters=min(k, max(1, len(embeddings))), n_init=10, random_state=0)
    return [int(x) for x in km.fit_predict(arr)]


def hybrid_cluster_labels(
    structural: list[list[str]],
    node_semantic_label: dict[str, int],
) -> list[dict[str, Any]]:
    """Attach majority semantic label per structural community (no merge of communities)."""
    out: list[dict[str, Any]] = []
    for i, comm in enumerate(structural):
        votes: dict[int, int] = {}
        for n in comm:
            lab = node_semantic_label.get(n)
            if lab is None:
                continue
            votes[lab] = votes.get(lab, 0) + 1
        majority = max(votes, key=votes.get) if votes else None
        out.append({"id": i, "members": comm, "semantic_majority": majority})
    return out


def communities_for_mode(
    g: CodeflowGraph,
    mode: str,
    *,
    max_undirected_nodes: int = 4000,
) -> tuple[list[Any], str]:
    """Return (communities_payload, algorithm_note)."""
    if mode in ("", "file_imports", "default"):
        comms = greedy_modularity_file_communities(g, max_undirected_nodes=max_undirected_nodes)
        return comms, "greedy_modularity_file_imports"
    if mode == "structural":
        comms = greedy_modularity_structural_communities(g, max_undirected_nodes=max_undirected_nodes)
        return comms, "greedy_modularity_structural_calls_imports"
    if mode == "semantic":
        _LOG.warning("semantic cluster_mode requires embeddings; no-op in scan pipeline")
        return [], "semantic_skipped_no_embeddings"
    if mode == "hybrid":
        struct = greedy_modularity_structural_communities(g, max_undirected_nodes=max_undirected_nodes)
        hybrid = hybrid_cluster_labels(struct, {})
        return hybrid, "hybrid_structural_with_empty_semantic"
    return greedy_modularity_file_communities(g, max_undirected_nodes=max_undirected_nodes), "greedy_modularity_file_imports"


def file_cluster_labels(
    g: CodeflowGraph,
    communities_payload: list[Any],
    mode: str,
) -> dict[str, int]:
    """Map normalized ``file_path`` strings to community id (last assignment wins on overlap)."""
    out: dict[str, int] = {}
    if not communities_payload:
        return out

    def assign_from_members(members: list[str], cid: int) -> None:
        for nid in members:
            fp = ""
            if isinstance(nid, str) and nid.startswith("file:"):
                fp = nid[5:].strip()
            elif isinstance(nid, str) and nid in g:
                fp = str(g.nodes[nid].get("file_path") or "").strip()
            if fp:
                out[fp] = cid

    if mode == "hybrid":
        for item in communities_payload:
            if isinstance(item, dict) and "members" in item:
                assign_from_members(list(item["members"]), int(item.get("id", 0)))
        return out

    for i, comm in enumerate(communities_payload):
        if isinstance(comm, list):
            assign_from_members(comm, i)
    return out
