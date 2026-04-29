from __future__ import annotations

from pathlib import Path

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.core.extractor import run_scan
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.detectors.entry_rank import entry_kind_rank, sort_entry_ids
from md_generator.codeflow.generators.entry_markdown import (
    pretty_start_method,
    type_label_for_kind,
    write_system_overview,
)
from md_generator.codeflow.generators.flow_summary import format_flow_description, format_method_summary_lines
from md_generator.codeflow.graph.builder import build_graph
from md_generator.codeflow.models.ir import EntryKind, EntryRecord, FileParseResult


def test_entry_kind_rank_order() -> None:
    assert entry_kind_rank(EntryKind.API_REST.value) == entry_kind_rank(EntryKind.PORTLET.value)
    assert entry_kind_rank(EntryKind.API_REST.value) < entry_kind_rank(EntryKind.KAFKA.value)
    assert entry_kind_rank(EntryKind.KAFKA.value) == entry_kind_rank(EntryKind.QUEUE.value)
    assert entry_kind_rank(EntryKind.SCHEDULER.value) < entry_kind_rank(EntryKind.MAIN.value)
    assert entry_kind_rank(EntryKind.MAIN.value) < entry_kind_rank(EntryKind.UNKNOWN.value)


def test_sort_entry_ids_stable_by_kind() -> None:
    g = nx.DiGraph()
    entries = [
        EntryRecord("b.py::Main.main", EntryKind.MAIN, "m", "b.py", 1),
        EntryRecord("a.py::Api.handler", EntryKind.API_REST, "GET /x", "a.py", 1),
        EntryRecord("c.py::Cons.run", EntryKind.KAFKA, "t", "c.py", 1),
    ]
    for e in entries:
        g.add_node(e.symbol_id, entry_kind=e.kind.value)
    ids = ["b.py::Main.main", "c.py::Cons.run", "a.py::Api.handler"]
    ranked = sort_entry_ids(ids, g, entries)
    assert ranked[0] == "a.py::Api.handler"
    assert ranked[1] == "c.py::Cons.run"
    assert ranked[2] == "b.py::Main.main"


def test_format_flow_description_branching() -> None:
    g = nx.DiGraph()
    for sid, cls, meth in (
        ("t.py::ClassA.a", "ClassA", "a"),
        ("t.py::ClassA.b", "ClassA", "b"),
        ("t.py::ClassA.c", "ClassA", "c"),
        ("t.py::ClassB.method1", "ClassB", "method1"),
        ("t.py::ClassB.method2", "ClassB", "method2"),
    ):
        g.add_node(sid, class_name=cls, method_name=meth, type="method")
    g.add_edge("t.py::ClassA.a", "t.py::ClassA.b", type="sync")
    g.add_edge(
        "t.py::ClassA.b",
        "t.py::ClassA.c",
        type="sync",
        condition="condition1 == true",
        labels=["condition1 == true"],
    )
    g.add_edge(
        "t.py::ClassA.b",
        "t.py::ClassB.method1",
        type="sync",
        condition="condition2 == true",
        labels=["condition2 == true"],
    )
    g.add_edge("t.py::ClassA.b", "t.py::ClassB.method2", type="sync")
    edge_rows = []
    for u, v in (
        ("t.py::ClassA.a", "t.py::ClassA.b"),
        ("t.py::ClassA.b", "t.py::ClassA.c"),
        ("t.py::ClassA.b", "t.py::ClassB.method1"),
        ("t.py::ClassA.b", "t.py::ClassB.method2"),
    ):
        edge_rows.append((u, v, dict(g.edges[u, v])))
    sl = FlowSlice(
        entry_id="t.py::ClassA.a",
        nodes=set(g.nodes),
        edges=edge_rows,
        depth=5,
    )
    text = "\n".join(format_flow_description(sl, g))
    assert "1. ClassA.a()" in text
    assert "→ calls ClassA.b()" in text
    assert "→ if (condition1 == true)" in text
    assert "ClassA.c()" in text
    assert "→ else" in text
    assert "method1()" in text or "ClassB.method1()" in text
    assert "method2()" in text or "ClassB.method2()" in text


def test_method_summary_headings() -> None:
    g = nx.DiGraph()
    g.add_node("t.py::ClassA.a", class_name="ClassA", method_name="a", type="entry")
    g.add_node("t.py::ClassA.b", class_name="ClassA", method_name="b", type="method")
    g.add_edge("t.py::ClassA.a", "t.py::ClassA.b", type="sync")
    sl = FlowSlice(
        entry_id="t.py::ClassA.a",
        nodes=set(g.nodes),
        edges=[(u, v, dict(g.edges[u, v])) for u, v in g.edges()],
        depth=5,
    )
    lines = format_method_summary_lines(sl, g, "t.py::ClassA.a")
    body = "\n".join(lines)
    assert "### ClassA" in body
    assert "- a() → start method" in body
    assert "- b() →" in body


def test_system_overview_contains_entry_links(tmp_path: Path) -> None:
    rows = [
        (
            "slug_a",
            "API",
            "Api.handler()",
            "[entry](./slug_a/entry.md)",
            "Api.handler() → …",
        ),
    ]
    p = tmp_path / "system_overview.md"
    write_system_overview(p, rows)
    content = p.read_text(encoding="utf-8")
    assert "system_overview" in content.lower() or "# System overview" in content
    assert "./slug_a/entry.md" in content


def test_run_scan_writes_entry_md_and_overview(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "mini_python"
    out = tmp_path / "scan_out"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        depth=4,
        languages="python",
    )
    run_scan(cfg)
    assert (out / "system_overview.md").is_file()
    found_entry = False
    for sub in out.iterdir():
        if sub.is_dir() and (sub / "entry.md").is_file():
            found_entry = True
            em = (sub / "entry.md").read_text(encoding="utf-8")
            assert "# Execution Flow Documentation" in em
            assert "## Entry Point" in em
            assert "## Flow Description" in em
            assert "## Method Summary" in em
    assert found_entry


def test_type_label_for_kind() -> None:
    assert type_label_for_kind(EntryKind.API_REST.value) == "API"
    assert type_label_for_kind(EntryKind.KAFKA.value) == "Event"


def test_pretty_start_method(tmp_path: Path) -> None:
    fr = FileParseResult(path=tmp_path / "x.py", language="python")
    fr.symbol_ids = ["x.py::Foo.bar"]
    fr.calls = []
    g = build_graph([fr], tmp_path).graph
    assert pretty_start_method(g, "x.py::Foo.bar") == "Foo.bar()"
