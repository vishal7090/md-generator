from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.api.schemas import scan_config_dump, scan_config_load
from md_generator.codeflow.core.extractor import run_scan
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.generators.business_rules_markdown import (
    write_business_rules_markdown,
    write_combined_entry_markdown,
)
from md_generator.codeflow.generators.entry_markdown import write_entry_markdown
from md_generator.codeflow.models.ir import BranchPoint, BusinessRule, FileParseResult
from md_generator.codeflow.rules.collector import collect_business_rules, dedupe_rules


def test_dedupe_rules_identical() -> None:
    r = BusinessRule(
        source="predicate",
        symbol_id="a",
        file_path="f.py",
        line=1,
        title="t",
        detail="same",
        confidence="high",
    )
    out = dedupe_rules([r, r])
    assert len(out) == 1


def test_collect_from_conditional_edges(tmp_path: Path) -> None:
    root = tmp_path
    g = nx.DiGraph()
    g.add_node("m.py::A.f", file_path="m.py", class_name="A", method_name="f", type="method")
    g.add_node("m.py::A.g", file_path="m.py", class_name="A", method_name="g", type="method")
    g.add_edge(
        "m.py::A.f",
        "m.py::A.g",
        type="sync",
        condition="x > 0",
        labels=["x > 0"],
    )
    sl = FlowSlice(
        entry_id="m.py::A.f",
        nodes=set(g.nodes),
        edges=[("m.py::A.f", "m.py::A.g", dict(g.edges["m.py::A.f", "m.py::A.g"]))],
        depth=3,
    )
    cfg = ScanConfig(
        project_root=root,
        output_path=root / "out",
        formats=("md",),
        business_rules=True,
        business_rules_sql=False,
    )
    rules = collect_business_rules("m.py::A.f", sl, g, [], cfg, project_root=root)
    assert any("x > 0" in r.detail for r in rules)


def test_sql_trigger_scan(tmp_path: Path) -> None:
    (tmp_path / "db.sql").write_text("-- hi\nCREATE TRIGGER trg BEFORE INSERT ON t BEGIN END;\n", encoding="utf-8")
    g = nx.DiGraph()
    g.add_node("m.py::A.f", file_path="m.py", type="method")
    sl = FlowSlice(entry_id="m.py::A.f", nodes={"m.py::A.f"}, edges=[], depth=3)
    cfg = ScanConfig(
        project_root=tmp_path,
        output_path=tmp_path / "out",
        formats=("md",),
        business_rules=True,
        business_rules_sql=True,
    )
    rules = collect_business_rules("m.py::A.f", sl, g, [], cfg, project_root=tmp_path)
    assert any(r.source == "sql_trigger" for r in rules)


def test_write_combined_merges_headings(tmp_path: Path) -> None:
    entry = tmp_path / "entry.md"
    rules_path = tmp_path / "business_rules.md"
    comb = tmp_path / "entry.combined.md"
    entry.write_text("# Execution Flow\n\nbody\n", encoding="utf-8")
    write_business_rules_markdown(rules_path, [], entry_hint="x")
    write_combined_entry_markdown(entry, rules_path, comb)
    text = comb.read_text(encoding="utf-8")
    assert "# Execution Flow" in text
    assert "# Business rules" in text
    assert "\n---\n" in text


def test_entry_markdown_includes_rules_section(tmp_path: Path) -> None:
    g = nx.DiGraph()
    g.add_node("k.py::M.x", file_path="k.py", class_name="M", method_name="x", type="entry")
    sl = FlowSlice(entry_id="k.py::M.x", nodes={"k.py::M.x"}, edges=[], depth=2)
    rlist = [
        BusinessRule(
            source="validation",
            symbol_id="k.py::M.x",
            file_path="k.py",
            line=3,
            title="Assert",
            detail="a == 1",
            confidence="low",
        ),
    ]
    write_entry_markdown(tmp_path / "e.md", "k.py::M.x", sl, g, None, rules=rlist)
    body = (tmp_path / "e.md").read_text(encoding="utf-8")
    assert "## Business rules" in body
    assert "business_rules.md" in body


def test_run_scan_emits_rules_artifacts(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "mini_python"
    out = tmp_path / "o"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        depth=4,
        languages="python",
        business_rules=True,
        business_rules_combined=True,
    )
    run_scan(cfg)
    found = False
    for sub in out.iterdir():
        if sub.is_dir() and (sub / "entry.md").is_file():
            found = True
            assert (sub / "business_rules.md").is_file()
            assert (sub / "entry.combined.md").is_file()
            combined = (sub / "entry.combined.md").read_text(encoding="utf-8")
            assert "Execution Flow Documentation" in combined
            assert "Business rules" in combined
    assert found


def test_run_scan_no_business_rules_skips_extra_files(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "mini_python"
    out = tmp_path / "o2"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        depth=4,
        languages="python",
        business_rules=False,
    )
    run_scan(cfg)
    for sub in out.iterdir():
        if sub.is_dir() and (sub / "entry.md").is_file():
            assert not (sub / "business_rules.md").exists()
            assert not (sub / "entry.combined.md").exists()
            em = (sub / "entry.md").read_text(encoding="utf-8")
            assert "## Business rules" not in em


def test_collect_returns_empty_when_business_rules_disabled(tmp_path: Path) -> None:
    g = nx.DiGraph()
    g.add_node("a.py::f", file_path="a.py")
    sl = FlowSlice(entry_id="a.py::f", nodes={"a.py::f"}, edges=[], depth=2)
    cfg = ScanConfig(
        project_root=tmp_path,
        output_path=tmp_path / "o",
        business_rules=False,
    )
    assert collect_business_rules("a.py::f", sl, g, [], cfg, project_root=tmp_path) == []


def test_collect_merges_file_parse_result_rules(tmp_path: Path) -> None:
    xpy = tmp_path / "x.py"
    xpy.write_text("class M:\n    def m(self):\n        pass\n", encoding="utf-8")
    g = nx.DiGraph()
    g.add_node("x.py::M.m", file_path="x.py")
    sl = FlowSlice(entry_id="x.py::M.m", nodes={"x.py::M.m"}, edges=[], depth=2)
    injected = BusinessRule(
        source="validation",
        symbol_id="x.py::M.m",
        file_path="x.py",
        line=9,
        title="From parser rules",
        detail="custom",
        confidence="high",
    )
    fr = FileParseResult(path=xpy, language="python")
    fr.rules.append(injected)
    cfg = ScanConfig(project_root=tmp_path, output_path=tmp_path / "o", business_rules=True)
    out = collect_business_rules("x.py::M.m", sl, g, [fr], cfg, project_root=tmp_path)
    assert any(r.title == "From parser rules" and r.detail == "custom" for r in out)


def test_collect_branch_points_from_parse_results(tmp_path: Path) -> None:
    ppy = tmp_path / "p.py"
    ppy.write_text("class C:\n    def run(self):\n        pass\n", encoding="utf-8")
    g = nx.DiGraph()
    g.add_node("p.py::C.run", file_path="p.py", class_name="C", method_name="run")
    sl = FlowSlice(entry_id="p.py::C.run", nodes={"p.py::C.run"}, edges=[], depth=2)
    fr = FileParseResult(path=ppy, language="python")
    fr.branches.append(
        BranchPoint(caller_id="p.py::C.run", kind="if", label="qty > 0", line=12),
    )
    cfg = ScanConfig(project_root=tmp_path, output_path=tmp_path / "o", business_rules=True)
    out = collect_business_rules("p.py::C.run", sl, g, [fr], cfg, project_root=tmp_path)
    br = [r for r in out if r.source == "branch"]
    assert len(br) == 1
    assert br[0].detail == "qty > 0"
    assert "Branch (if)" in br[0].title


def test_collect_python_field_validator_assert_and_raise(tmp_path: Path) -> None:
    root = tmp_path
    mod = root / "mod.py"
    mod.write_text(
        '''\
class M:
    @field_validator("x")
    @classmethod
    def validate_x(cls, v):
        return v

    def f(self):
        assert 1 == 1
        raise ValueError("invalid input")
''',
        encoding="utf-8",
    )
    g = nx.DiGraph()
    g.add_node("mod.py::M.validate_x", file_path="mod.py", class_name="M", method_name="validate_x", type="method")
    g.add_node("mod.py::M.f", file_path="mod.py", class_name="M", method_name="f", type="method")
    sl = FlowSlice(
        entry_id="mod.py::M.f",
        nodes={"mod.py::M.f", "mod.py::M.validate_x"},
        edges=[],
        depth=2,
    )
    fr = FileParseResult(path=mod, language="python")
    cfg = ScanConfig(project_root=root, output_path=root / "out", business_rules=True)
    out = collect_business_rules("mod.py::M.f", sl, g, [fr], cfg, project_root=root)
    titles = [r.title for r in out]
    assert any("field_validator" in t for t in titles)
    assert any(t == "Assert" for t in titles)
    assert any("Raise ValueError" in t for t in titles)


def test_write_business_rules_markdown_non_empty_sections(tmp_path: Path) -> None:
    rules = [
        BusinessRule(
            source="predicate",
            symbol_id="a::X",
            file_path="f.py",
            line=1,
            title="t1",
            detail="d1",
            confidence="high",
        ),
        BusinessRule(
            source="branch",
            symbol_id="a::X",
            file_path="f.py",
            line=4,
            title="Branch (if)",
            detail="flag set",
            confidence="medium",
        ),
        BusinessRule(
            source="validation",
            symbol_id="a::X",
            file_path="f.py",
            line=2,
            title="t2",
            detail="d2",
            confidence="low",
        ),
        BusinessRule(
            source="sql_trigger",
            symbol_id=None,
            file_path="s.sql",
            line=3,
            title="SQL trigger",
            detail="CREATE TRIGGER trg",
            confidence="medium",
        ),
    ]
    path = tmp_path / "br.md"
    write_business_rules_markdown(path, rules, entry_hint="e1")
    text = path.read_text(encoding="utf-8")
    assert "## Predicates and branch conditions (from call graph)" in text
    assert "## Branch points (parser)" in text
    assert "## Validation-style hints (assert, raise, decorators)" in text
    assert "## SQL triggers (workspace scan)" in text
    assert "| Line | Symbol | Title | Detail | Conf. |" in text
    assert "| 1 |" in text


def test_run_scan_combined_disabled_writes_no_combined_file(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "mini_python"
    out = tmp_path / "o3"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        depth=4,
        languages="python",
        business_rules=True,
        business_rules_combined=False,
    )
    run_scan(cfg)
    for sub in out.iterdir():
        if sub.is_dir() and (sub / "entry.md").is_file():
            assert (sub / "business_rules.md").is_file()
            assert not (sub / "entry.combined.md").exists()


def test_sql_scan_respects_paths_override_parent(tmp_path: Path) -> None:
    sub = tmp_path / "pkg"
    other = tmp_path / "other"
    sub.mkdir()
    other.mkdir()
    (sub / "in.sql").write_text("CREATE TRIGGER t1 BEFORE INSERT ON a;\n", encoding="utf-8")
    (other / "out.sql").write_text("CREATE TRIGGER t2 BEFORE DELETE ON b;\n", encoding="utf-8")
    (sub / "marker.py").write_text("x = 1\n", encoding="utf-8")

    g = nx.DiGraph()
    g.add_node("pkg/marker.py::x", file_path="pkg/marker.py")
    sl = FlowSlice(entry_id="pkg/marker.py::x", nodes={"pkg/marker.py::x"}, edges=[], depth=2)
    cfg = ScanConfig(
        project_root=tmp_path,
        output_path=tmp_path / "out",
        business_rules=True,
        business_rules_sql=True,
        paths_override=[sub / "marker.py"],
    )
    rules = collect_business_rules("pkg/marker.py::x", sl, g, [], cfg, project_root=tmp_path)
    sql_rules = [r for r in rules if r.source == "sql_trigger"]
    assert len(sql_rules) == 1
    assert "t1" in sql_rules[0].detail
    assert "t2" not in sql_rules[0].detail


def test_scan_config_dump_load_roundtrip_business_flags(tmp_path: Path) -> None:
    cfg = ScanConfig(
        project_root=tmp_path,
        output_path=tmp_path / "o",
        business_rules=False,
        business_rules_sql=True,
        business_rules_combined=False,
    )
    raw = json.dumps(scan_config_dump(cfg))
    cfg2 = scan_config_load(json.loads(raw))
    assert cfg2.business_rules is False
    assert cfg2.business_rules_sql is True
    assert cfg2.business_rules_combined is False


def test_cli_no_business_rules_combined(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "mini_python"
    out = tmp_path / "cli_out"
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "md_generator.codeflow.cli.main",
            "scan",
            str(root),
            "--output",
            str(out),
            "--depth",
            "3",
            "--formats",
            "md",
            "--no-business-rules-combined",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    found = False
    for sub in out.iterdir():
        if sub.is_dir() and (sub / "entry.md").is_file():
            found = True
            assert (sub / "business_rules.md").is_file()
            assert not (sub / "entry.combined.md").exists()
    assert found


def test_cli_no_business_rules(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "mini_python"
    out = tmp_path / "cli_out2"
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "md_generator.codeflow.cli.main",
            "scan",
            str(root),
            "--output",
            str(out),
            "--depth",
            "3",
            "--formats",
            "md",
            "--no-business-rules",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    for sub in out.iterdir():
        if sub.is_dir() and (sub / "entry.md").is_file():
            assert not (sub / "business_rules.md").exists()
            assert not (sub / "entry.combined.md").exists()
