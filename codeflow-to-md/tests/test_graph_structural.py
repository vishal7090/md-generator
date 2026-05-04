from __future__ import annotations

from pathlib import Path

import networkx as nx

from md_generator.codeflow.graph.builder import build_graph
from md_generator.codeflow.graph.enricher import (
    called_by_transitive,
    subgraph_by_relations,
)
from md_generator.codeflow.graph.export_schema import to_stable_schema
from md_generator.codeflow.graph.relations import REL_CALLS, REL_IMPLEMENTS, REL_IMPORTS, REL_INHERITS
from md_generator.codeflow.models.ir import FileParseResult, StructuralEdge
from md_generator.codeflow.parsers.java_parser import JavaParser


def test_java_parser_emits_structural_edges(tmp_path: Path) -> None:
    root = tmp_path / "jp"
    root.mkdir()
    j = root / "Demo.java"
    j.write_text(
        "package com.example;\n"
        "import java.util.List;\n"
        "public class Demo extends Base implements Runnable {\n"
        "  public void run() {}\n"
        "}\n",
        encoding="utf-8",
    )
    pr = JavaParser().parse_file(j, root)
    assert pr.java_package == "com.example"
    kinds = {e.relation for e in pr.structural_edges}
    assert REL_IMPORTS in kinds
    assert REL_INHERITS in kinds
    assert any("java.util.List" in e.target_id for e in pr.structural_edges if e.relation == REL_IMPORTS)


def test_build_graph_merges_structural_when_enabled(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    j = root / "A.java"
    j.write_text(
        "package p;\n"
        "import java.io.Serializable;\n"
        "class A implements Serializable { void m() {} }\n",
        encoding="utf-8",
    )
    pr = JavaParser().parse_file(j, root)
    g0 = build_graph([pr], root, include_structural=False).graph
    g1 = build_graph([pr], root, include_structural=True).graph
    assert g1.number_of_nodes() >= g0.number_of_nodes()
    assert any(str(n).startswith("file:") for n in g1.nodes)
    rels = {ed.get("relation") for _, _, ed in g1.edges(data=True)}
    assert REL_IMPORTS in rels or REL_INHERITS in rels


def test_called_by_transitive() -> None:
    g = nx.DiGraph()
    g.add_edge("a", "b", relation=REL_CALLS)
    g.add_edge("b", "c", relation=REL_CALLS)
    out = called_by_transitive(g, "c", cap=10)
    assert "a" in out and "b" in out


def test_subgraph_by_relations_filters() -> None:
    g = nx.DiGraph()
    g.add_node("x")
    g.add_node("y")
    g.add_edge("x", "y", relation=REL_IMPORTS)
    g.add_edge("y", "x", relation=REL_CALLS)
    sg = subgraph_by_relations(g, {REL_IMPORTS})
    assert sg.has_edge("x", "y")
    assert not sg.has_edge("y", "x")


def test_to_stable_schema_emits_structural_edges(tmp_path: Path) -> None:
    root = tmp_path / "s"
    root.mkdir()
    j = root / "A.java"
    j.write_text(
        "package p;\n"
        "import java.io.Serializable;\n"
        "class A implements Serializable { void m() {} }\n",
        encoding="utf-8",
    )
    pr = JavaParser().parse_file(j, root)
    g = build_graph([pr], root, include_structural=True).graph
    sch = to_stable_schema(g)
    kinds = {e["kind"] for e in sch["edges"]}
    assert REL_IMPORTS in kinds
    assert REL_IMPLEMENTS in kinds
