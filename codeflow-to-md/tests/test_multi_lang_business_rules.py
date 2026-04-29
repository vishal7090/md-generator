from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.graph.builder import build_graph
from md_generator.codeflow.parsers.base import ParserRegistry, register_defaults
from md_generator.codeflow.parsers.go_parser import GoParser
from md_generator.codeflow.rules.collector import collect_business_rules
from md_generator.codeflow.core.run_config import ScanConfig


def test_javascript_call_has_condition_label(tmp_path: Path) -> None:
    p = tmp_path / "sample.js"
    p.write_text(
        "function g() {}\nfunction f(x) { if (x > 0) { g(); } }\n",
        encoding="utf-8",
    )
    reg = ParserRegistry()
    register_defaults(reg)
    pr = reg.parse_file(p, tmp_path, "javascript")
    assert pr is not None
    gb = build_graph([pr], tmp_path)
    g = gb.graph
    caller = "sample.js::f"
    cond_edges = [v for v in g.successors(caller) if g.edges[caller, v].get("condition")]
    assert cond_edges, "expected conditional edge from f()"


def test_javascript_throw_in_rules_slice(tmp_path: Path) -> None:
    p = tmp_path / "t.js"
    p.write_text(
        "function f() { if (true) { throw new Error('x'); } }\n",
        encoding="utf-8",
    )
    reg = ParserRegistry()
    register_defaults(reg)
    pr = reg.parse_file(p, tmp_path, "javascript")
    assert pr is not None and pr.rules
    g = nx.DiGraph()
    sid = "t.js::f"
    g.add_node(sid, file_path="t.js", type="method")
    sl = FlowSlice(entry_id=sid, nodes={sid}, edges=[], depth=3)
    cfg = ScanConfig(project_root=tmp_path, output_path=tmp_path / "o", formats=("md",), business_rules=True)
    rules = collect_business_rules(sid, sl, g, [pr], cfg, project_root=tmp_path)
    assert any("Throw" in r.title for r in rules)


@pytest.mark.skipif(shutil.which("go") is None, reason="go not on PATH")
def test_go_call_condition_and_rule(tmp_path: Path) -> None:
    p = tmp_path / "m.go"
    p.write_text(
        "package main\nfunc h() {}\nfunc f(x int) {\n\tif x > 0 {\n\t\th()\n\t}\n\tpanic(\"boom\")\n}\n",
        encoding="utf-8",
    )
    pr = GoParser().parse_file(p, tmp_path)
    assert pr.calls, "expected calls from go dump"
    assert any(c.condition_label for c in pr.calls), "expected if-condition on call edge metadata"
    assert pr.rules, "expected panic rule from go dump"


def test_cpp_rules_throw(tmp_path: Path) -> None:
    try:
        import tree_sitter_cpp as tscpp  # noqa: F401
    except ImportError:
        pytest.skip("tree-sitter-cpp not installed")
    p = tmp_path / "x.cpp"
    p.write_text(
        "void g() {}\nvoid f() {\n  if (1) { g(); }\n  throw 1;\n}\n",
        encoding="utf-8",
    )
    from md_generator.codeflow.rules.cpp_rules import extract_cpp_method_rules

    key = "x.cpp"
    sid = f"{key}::f"
    rules = extract_cpp_method_rules(p, tmp_path, {sid})
    assert any("Throw" in r.title for r in rules)
