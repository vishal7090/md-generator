from __future__ import annotations

import numpy as np

from md_generator.codeflow.graph.semantic_index import SemanticIndex


def test_semantic_index_search_ordering() -> None:
    # Three normalized 2D vectors; query aligns with middle row
    ids = ["a", "b", "c"]
    v = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float64)
    # normalize rows
    v = v / np.linalg.norm(v, axis=1, keepdims=True)
    idx = SemanticIndex()
    idx.build(ids, v)
    q = np.array([0.0, 1.0], dtype=np.float64)
    q = q / np.linalg.norm(q)
    hits = idx.search(q, top_k=2, exclude=set())
    assert hits[0][0] == "b"
    assert hits[0][1] > hits[1][1]


def test_semantic_index_exclude() -> None:
    ids = ["x", "y"]
    v = np.eye(2, dtype=np.float64)
    idx = SemanticIndex()
    idx.build(ids, v)
    q = np.array([1.0, 0.0], dtype=np.float64)
    hits = idx.search(q, top_k=1, exclude={"x"})
    assert hits[0][0] == "y"


def test_search_subset() -> None:
    ids = ["a", "b", "c"]
    v = np.eye(3, dtype=np.float64)
    idx = SemanticIndex()
    idx.build(ids, v)
    q = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    hits = idx.search_subset({"a", "c"}, q, top_k=2)
    assert hits[0][0] == "a"
