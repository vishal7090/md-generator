"""NL query parsing and execution (no SentenceTransformer)."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph.nl_query import (
    execute_nl_intent,
    parse_nl_query,
    resolve_target_hint,
)


def _graph() -> nx.MultiDiGraph:
    g: nx.MultiDiGraph = nx.MultiDiGraph()
    g.add_node("p::A.foo", type="method", method_name="foo", class_name="A")
    g.add_node("p::A.bar", type="method", method_name="bar", class_name="A")
    g.add_node("p::B.baz", type="method", method_name="baz", class_name="B")
    g.add_edge("p::A.foo", "p::A.bar", relation="CALLS")
    return g


def test_parse_semantic_and_called_by() -> None:
    p = parse_nl_query("find similar flows for billing")
    assert p["type"] == "semantic_search"
    p2 = parse_nl_query("who calls foo")
    assert p2["type"] == "called_by"
    assert p2.get("target_hint")


def test_parse_impact() -> None:
    p = parse_nl_query("what is impacted by A.foo")
    assert p["type"] == "impact"


def test_resolve_unique() -> None:
    g = _graph()
    nid, amb = resolve_target_hint(g, "foo")
    assert nid == "p::A.foo"
    assert amb == []


def test_execute_semantic_fallback() -> None:
    g = _graph()
    r = execute_nl_intent(g, parse_nl_query("similar to foo"), semantic_artifacts=None, top_k=5)
    assert r["intent"] == "semantic_search"
    assert r["source"] == "substring_fallback"


def test_execute_called_by() -> None:
    g = _graph()
    r = execute_nl_intent(g, parse_nl_query("called by bar"), semantic_artifacts=None, list_cap=20)
    assert r["intent"] == "called_by"
    assert "target" in r
