"""Enterprise graph: dependency reachability, file-layer imports, clustering, SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import networkx as nx

from md_generator.codeflow.graph.analysis import (
    dependency_reachability_subgraph,
    impact_descendants_dependency,
)
from md_generator.codeflow.graph.builder import build_graph
from md_generator.codeflow.graph.clustering import greedy_modularity_file_communities
from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import edge_data_dicts
from md_generator.codeflow.graph.sqlite_export import export_graph_sqlite
from md_generator.codeflow.models.ir import FileParseResult, StructuralEdge


def test_dependency_reachability_excludes_contains() -> None:
    g = nx.DiGraph()
    g.add_node("F", type="file")
    g.add_node("M", type="method", file_path="x")
    g.add_node("N", type="method")
    g.add_node("Z", type="external")
    g.add_edge("F", "M", relation=rel.REL_CONTAINS, confidence=1.0)
    g.add_edge("M", "N", relation=rel.REL_CALLS, confidence=1.0)
    g.add_edge("M", "Z", relation=rel.REL_IMPORTS, confidence=0.8)
    dg = dependency_reachability_subgraph(g)
    assert not dg.has_edge("F", "M")
    assert set(nx.descendants(dg, "M")) == {"N", "Z"}
    imp = impact_descendants_dependency(g, "M", cap=100)
    assert set(imp) == {"N", "Z"}


def test_file_level_import_edge_from_class_import(tmp_path: Path) -> None:
    root = tmp_path
    fr = FileParseResult(path=root / "src" / "A.java", language="java", java_package="p")
    fr.structural_edges.append(
        StructuralEdge(
            source_id="class:src/A.java::A",
            target_id="class:src/B.java::B",
            relation=rel.REL_IMPORTS,
            confidence=1.0,
            line=1,
        ),
    )
    gb = build_graph([fr], root, include_structural=True)
    g = gb.graph
    assert g.has_edge("file:src/A.java", "file:src/B.java")
    ed = edge_data_dicts(g, "file:src/A.java", "file:src/B.java")[0]
    assert ed.get("relation") == rel.REL_IMPORTS
    assert ed.get("file_layer") is True


def test_greedy_modularity_file_triangle() -> None:
    g = nx.DiGraph()
    for p in ("a", "b", "c"):
        nid = f"file:{p}.java"
        g.add_node(nid, type="file", language="java")
    g.add_edge("file:a.java", "file:b.java", relation=rel.REL_IMPORTS, confidence=1.0)
    g.add_edge("file:b.java", "file:c.java", relation=rel.REL_IMPORTS, confidence=1.0)
    g.add_edge("file:c.java", "file:a.java", relation=rel.REL_IMPORTS, confidence=1.0)
    comms = greedy_modularity_file_communities(g)
    assert len(comms) >= 1
    assert {n for c in comms for n in c} == {"file:a.java", "file:b.java", "file:c.java"}


def test_export_graph_sqlite_counts(tmp_path: Path) -> None:
    g = nx.DiGraph()
    g.add_node("a", type="method")
    g.add_node("b", type="method")
    g.add_edge("a", "b", relation=rel.REL_CALLS, confidence=1.0)
    dbp = tmp_path / "g.db"
    export_graph_sqlite(dbp, g)
    conn = sqlite3.connect(str(dbp))
    try:
        n = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        assert n == 2
        assert e == 1
    finally:
        conn.close()


def test_export_schema_async_duplicate_edge() -> None:
    from md_generator.codeflow.graph.export_schema import to_stable_schema

    g = nx.DiGraph()
    g.add_node("x.java::A.m", type="method", file_path="x.java", class_name="A", method_name="m", language="java")
    g.add_node("y.java::B.n", type="method", file_path="y.java", class_name="B", method_name="n", language="java")
    g.add_edge(
        "x.java::A.m",
        "y.java::B.n",
        relation=rel.REL_CALLS,
        confidence=1.0,
        async_=True,
        type="async",
    )
    sch = to_stable_schema(g)
    kinds = [e["kind"] for e in sch["edges"] if e["source"] == "x.java::A.m" and e["target"] == "y.java::B.n"]
    assert rel.REL_CALLS in kinds
    assert rel.REL_ASYNC in kinds
