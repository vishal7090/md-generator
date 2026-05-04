from __future__ import annotations

import json
from pathlib import Path

from md_generator.codeflow.core.extractor import run_scan
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.graph.builder import build_graph
from md_generator.codeflow.parsers.java_parser import JavaParser
from md_generator.codeflow.rules.collector import collect_business_rules
from md_generator.codeflow.analyzers.flow_analyzer import slice_from_entry
from md_generator.codeflow.graph.multigraph_utils import edge_data_dicts


def _fixture_root(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / name


def test_java_callsite_condition_on_edge(tmp_path: Path) -> None:
    root = _fixture_root("java_cond")
    path = root / "c" / "Cond.java"
    pr = JavaParser().parse_file(path, root)
    assert pr.language == "java"
    gb = build_graph([pr], root)
    g = gb.graph
    caller = "c/Cond.java::Cond.caller"
    assert caller in g
    cond_edges = [
        (v, d.get("condition"))
        for v in g.successors(caller)
        for d in edge_data_dicts(g, caller, v)
        if d.get("condition")
    ]
    assert cond_edges, "expected at least one conditional call from caller()"
    _v, cond = cond_edges[0]
    assert cond is not None
    assert "userIsActive" in cond or "if" in cond.lower() or "(" in cond


def test_java_business_rules_from_collector(tmp_path: Path) -> None:
    root = _fixture_root("java_rules")
    path = root / "r" / "RulesBean.java"
    pr = JavaParser().parse_file(path, root)
    gb = build_graph([pr], root)
    g = gb.graph
    sid = "r/RulesBean.java::RulesBean.save"
    sl = slice_from_entry(g, sid, max_depth=5)
    cfg = ScanConfig(
        project_root=root,
        output_path=tmp_path / "out",
        formats=("md",),
        languages="java",
        business_rules=True,
    )
    rules = collect_business_rules(sid, sl, g, [pr], cfg, project_root=root)
    titles = " ".join(r.title for r in rules)
    assert "NotNull" in titles or "Throw" in titles


def test_java_branches_emitted_on_parse_result(tmp_path: Path) -> None:
    root = _fixture_root("java_cond")
    path = root / "c" / "Cond.java"
    pr = JavaParser().parse_file(path, root)
    assert any(b.kind == "if" for b in pr.branches)


def test_run_scan_entry_fallback_none_writes_summary(tmp_path: Path) -> None:
    """No Java entries: with entry_fallback=none, no slug dirs and summary warns."""
    root = _fixture_root("java_cond")
    out = tmp_path / "out"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        languages="java",
        entry_fallback="none",
        business_rules=False,
    )
    run_scan(cfg)
    summary = (out / "scan-summary.md").read_text(encoding="utf-8")
    assert "entry_fallback" in summary
    slug_dirs = [p for p in out.iterdir() if p.is_dir()]
    assert slug_dirs == []


def test_emit_entry_per_method_creates_multiple_slugs(tmp_path: Path) -> None:
    root = _fixture_root("java_cond")
    out = tmp_path / "out2"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        languages="java",
        emit_entry_per_method=True,
        emit_entry_max=50,
        business_rules=False,
    )
    run_scan(cfg)
    methods = out / "methods"
    assert methods.is_dir()
    dirs = [p.name for p in methods.iterdir() if p.is_dir()]
    assert len(dirs) >= 3


def test_emit_graph_schema_writes_json(tmp_path: Path) -> None:
    root = _fixture_root("java_cond")
    out = tmp_path / "out_schema"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("json",),
        languages="java",
        emit_graph_schema=True,
        business_rules=False,
    )
    run_scan(cfg)
    path = out / "graph-schema.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "nodes" in data and "edges" in data


def test_java_inner_class_symbol_in_graph(tmp_path: Path) -> None:
    root = _fixture_root("java_inner")
    path = root / "inner" / "InnerHost.java"
    pr = JavaParser().parse_file(path, root)
    inner_sid = "inner/InnerHost.java::InnerHost.Inner.innerMethod"
    assert any("InnerHost.Inner.innerMethod" in s or "Inner.innerMethod" in s for s in pr.symbol_ids)
    gb = build_graph([pr], root)
    assert inner_sid in gb.graph


def test_entries_file_selects_subset(tmp_path: Path) -> None:
    root = _fixture_root("java_cond")
    entries_path = tmp_path / "entries.txt"
    entries_path.write_text("c/Cond.java::Cond.caller\n", encoding="utf-8")
    out = tmp_path / "out3"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        languages="java",
        entries_file=entries_path,
        business_rules=False,
    )
    run_scan(cfg)
    dirs = [p for p in out.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    assert "caller" in dirs[0].name


def test_graph_json_contains_condition_for_java(tmp_path: Path) -> None:
    root = _fixture_root("java_cond")
    out = tmp_path / "out4"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("json",),
        languages="java",
        emit_entry_per_method=True,
        emit_entry_max=5,
        business_rules=False,
    )
    run_scan(cfg)
    full = json.loads((out / "graph-full.json").read_text(encoding="utf-8"))
    edges = full["edges"]
    hit = next(
        (
            e
            for e in edges
            if e.get("source", "").endswith("Cond.caller") and (e.get("condition") or (e.get("labels") or []))
        ),
        None,
    )
    assert hit is not None
    assert hit.get("condition") or (hit.get("labels") and hit["labels"][0])
