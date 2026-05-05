"""Semantic artifacts with mocked encode (no model download)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from md_generator.codeflow.graph.semantic_enricher import attach_semantic_groups, build_semantic_artifacts


def _graph_two_methods() -> nx.MultiDiGraph:
    g: nx.MultiDiGraph = nx.MultiDiGraph()
    g.add_node(
        "demo::Foo.a",
        type="method",
        method_name="a",
        class_name="Foo",
        file_path="demo/Foo.java",
        language="java",
    )
    g.add_node(
        "demo::Foo.b",
        type="method",
        method_name="b",
        class_name="Foo",
        file_path="demo/Foo.java",
        language="java",
    )
    g.add_edge("demo::Foo.a", "demo::Foo.b", relation="CALLS")
    return g


def test_build_semantic_artifacts_mocked_encode(tmp_path: Path) -> None:
    g = _graph_two_methods()

    def fake_encode(texts: list[str], _mid: str) -> np.ndarray:
        # Two distinct rows so KMeans can split if k=2
        return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)

    art = build_semantic_artifacts(
        g,
        tmp_path,
        model_id="mock-model",
        max_nodes=5000,
        k_semantic=2,
        encode_fn=fake_encode,
    )
    assert art is not None
    assert len(art.node_ids) == 2
    assert set(art.labels.keys()) == {"demo::Foo.a", "demo::Foo.b"}
    sim = art.index.search(art.vectors[0], top_k=2, exclude={"demo::Foo.a"})
    assert sim and sim[0][0] == "demo::Foo.b"

    attach_semantic_groups(g, art.labels)
    assert g.nodes["demo::Foo.a"]["semantic_group"] == art.labels["demo::Foo.a"]


def test_neighbors_serializable_shape(tmp_path: Path) -> None:
    from md_generator.codeflow.api.semantic_api import neighbors_serializable

    g = _graph_two_methods()
    art = build_semantic_artifacts(
        g,
        tmp_path,
        model_id="m2",
        max_nodes=5000,
        k_semantic=2,
        encode_fn=lambda texts, mid: np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
    )
    assert art is not None
    rows = neighbors_serializable(art, "demo::Foo.a", 5, g)
    assert len(rows) >= 1
    assert "node_id" in rows[0] and "score" in rows[0]
