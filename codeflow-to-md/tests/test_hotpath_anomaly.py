"""Runtime trace normalization, hot paths, CFG anomalies."""

from __future__ import annotations

from md_generator.codeflow.graph.anomaly import rare_cfg_edges
from md_generator.codeflow.graph.cfg_model import CFG, CFGEdge, CFGNode
from md_generator.codeflow.graph.hotpath import normalize_runtime_trace, score_cfg_paths, top_hot_paths


def test_normalize_counts_and_edges_alias() -> None:
    t = {"counts": {"a->b": 10}, "edges": {"b->c": 5}}
    m = normalize_runtime_trace(t)
    assert m["a->b"] == 10.0 and m["b->c"] == 5.0


def test_hot_path_scoring() -> None:
    paths = [["s", "m", "e"], ["s", "x", "e"]]
    counts = {"s->m": 100, "m->e": 50, "s->x": 1, "x->e": 1}
    scored = score_cfg_paths(paths, counts)
    assert scored[0][1] >= scored[1][1]
    top = top_hot_paths(paths, counts, top_n=1)
    assert top[0]["score"] == 150.0


def test_rare_edge_below_threshold() -> None:
    c = CFG(
        nodes={
            "a": CFGNode("a", "X", "", "", ""),
            "b": CFGNode("b", "X", "", "", ""),
            "c": CFGNode("c", "X", "", "", ""),
        },
        edges=[
            CFGEdge("a", "b"),
            CFGEdge("b", "c"),
        ],
    )
    trace = {"counts": {"a->b": 95, "b->c": 5}}
    rare = rare_cfg_edges(c, trace, frequency_threshold=0.06)
    keys = {(x["source"], x["target"]) for x in rare}
    assert ("b", "c") in keys
