"""Clustering semantic / hybrid paths with explicit labels."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph.clustering import communities_for_mode


def _tiny_graph() -> nx.MultiDiGraph:
    g: nx.MultiDiGraph = nx.MultiDiGraph()
    for nid in ("pkg::A.m1", "pkg::A.m2", "pkg::B.m1"):
        g.add_node(nid, type="method")
    g.add_edge("pkg::A.m1", "pkg::B.m1", relation="CALLS")
    return g


def test_semantic_mode_groups_by_label() -> None:
    g = _tiny_graph()
    labels = {"pkg::A.m1": 0, "pkg::A.m2": 0, "pkg::B.m1": 1}
    comms, algo = communities_for_mode(g, "semantic", semantic_labels=labels)
    assert algo == "kmeans_embeddings"
    assert len(comms) == 2
    flat = {n for c in comms for n in c}
    assert flat == {"pkg::A.m1", "pkg::A.m2", "pkg::B.m1"}


def test_hybrid_mode_with_semantic_majority() -> None:
    g = _tiny_graph()
    labels = {"pkg::A.m1": 7, "pkg::A.m2": 7, "pkg::B.m1": 3}
    comms, algo = communities_for_mode(g, "hybrid", semantic_labels=labels)
    assert algo == "hybrid_structural_kmeans"
    assert comms and isinstance(comms[0], dict)
    assert "semantic_majority" in comms[0]
