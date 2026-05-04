from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.core.extractor import run_scan
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.graph.call_expander import expand_cfg_calls
from md_generator.codeflow.graph.cfg_builder import build_cfg_from_ir
from md_generator.codeflow.graph.path_enumerator import enumerate_paths, find_cfg_end_id, find_cfg_start_id
from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt
from md_generator.codeflow.parsers.adapters.java_adapter import populate_ir_methods_java
from md_generator.codeflow.parsers.adapters.python_adapter import populate_ir_methods_python


def test_build_cfg_from_ir_simple_if() -> None:
    ir = IRMethod(
        symbol_id="m.py::f",
        name="f",
        file_path="m.py",
        language="python",
        body=(
            IRStmt(
                kind="IF",
                condition="x",
                body=(IRStmt(kind="CALL", target="a", line=2),),
                else_body=(IRStmt(kind="CALL", target="b", line=3),),
                line=1,
            ),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=100)
    assert "START" in "".join(n.kind for n in cfg.nodes.values())
    assert any(e.label == "then" for e in cfg.edges)
    assert any(e.label == "else" for e in cfg.edges)


def test_enumerate_paths_if_else_two_paths() -> None:
    ir = IRMethod(
        symbol_id="m.py::f",
        name="f",
        file_path="m.py",
        language="python",
        body=(
            IRStmt(
                kind="IF",
                condition="x",
                body=(IRStmt(kind="CALL", target="a", line=2),),
                else_body=(IRStmt(kind="CALL", target="b", line=3),),
                line=1,
            ),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=100)
    s, e = find_cfg_start_id(cfg), find_cfg_end_id(cfg)
    assert s and e
    res = enumerate_paths(cfg, s, e, max_paths=50, max_depth=200, max_loop_visits=2)
    assert len(res.paths) == 2
    assert not res.truncated
    ends = {tuple(p) for p in res.paths}
    assert len(ends) == 2


def test_enumerate_paths_nested_if_multiple_paths() -> None:
    ir = IRMethod(
        symbol_id="m.py::g",
        name="g",
        file_path="m.py",
        language="python",
        body=(
            IRStmt(
                kind="IF",
                condition="a",
                body=(
                    IRStmt(
                        kind="IF",
                        condition="b",
                        body=(IRStmt(kind="CALL", target="c1", line=3),),
                        else_body=(IRStmt(kind="CALL", target="c2", line=4),),
                        line=2,
                    ),
                ),
                else_body=(IRStmt(kind="CALL", target="c3", line=5),),
                line=1,
            ),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=200)
    s, e = find_cfg_start_id(cfg), find_cfg_end_id(cfg)
    assert s and e
    res = enumerate_paths(cfg, s, e, max_paths=100, max_depth=500, max_loop_visits=2)
    assert len(res.paths) >= 3
    assert len({tuple(p) for p in res.paths}) == len(res.paths)


def test_enumerate_paths_loop_bounded_and_truncated() -> None:
    ir = IRMethod(
        symbol_id="m.py::h",
        name="h",
        file_path="m.py",
        language="python",
        body=(
            IRStmt(
                kind="LOOP",
                condition="items",
                body=(IRStmt(kind="CALL", target="work", line=2),),
                line=1,
            ),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=100)
    s, e = find_cfg_start_id(cfg), find_cfg_end_id(cfg)
    assert s and e
    res = enumerate_paths(cfg, s, e, max_paths=500, max_depth=2000, max_loop_visits=1)
    assert len(res.paths) >= 1
    res2 = enumerate_paths(cfg, s, e, max_paths=2, max_depth=2000, max_loop_visits=2)
    assert len(res2.paths) <= 2
    assert res2.truncated or len(res2.paths) <= 2


def test_populate_ir_python_fixture(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    p = root / "mod.py"
    p.write_text(
        "def foo():\n"
        "    if x:\n"
        "        bar()\n"
        "    else:\n"
        "        baz()\n",
        encoding="utf-8",
    )
    from md_generator.codeflow.models.ir import FileParseResult

    fr = FileParseResult(path=p.resolve(), language="python")
    populate_ir_methods_python(fr, root)
    assert len(fr.ir_methods) >= 1
    foo = next(m for m in fr.ir_methods if m.name == "foo")
    cfg = build_cfg_from_ir(foo, max_nodes=200)
    assert len(cfg.nodes) >= 3


def test_populate_ir_java_simple(tmp_path: Path) -> None:
    root = tmp_path / "jp"
    root.mkdir()
    j = root / "Hello.java"
    j.write_text(
        "class Hello {\n"
        "  void m() {\n"
        "    if (true) { x(); } else { y(); }\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    from md_generator.codeflow.models.ir import FileParseResult

    fr = FileParseResult(path=j.resolve(), language="java")
    populate_ir_methods_java(fr, root)
    assert any(m.name == "m" for m in fr.ir_methods)


def test_treesitter_adapter_when_installed(tmp_path: Path) -> None:
    try:
        from md_generator.codeflow.parsers.adapters.treesitter_adapter import populate_ir_methods_treesitter
    except ImportError:
        return
    root = tmp_path / "tsproj"
    root.mkdir()
    f = root / "a.ts"
    f.write_text("function f() { if (true) { g(); } }\n", encoding="utf-8")
    from md_generator.codeflow.models.ir import FileParseResult

    fr = FileParseResult(path=f.resolve(), language="typescript")
    populate_ir_methods_treesitter(fr, root)
    assert fr.ir_methods


def test_expand_cfg_calls_cross_method() -> None:
    ir_foo = IRMethod(
        symbol_id="m.py::foo",
        name="foo",
        file_path="m.py",
        language="python",
        body=(IRStmt(kind="CALL", target="bar", line=1),),
    )
    ir_bar = IRMethod(
        symbol_id="m.py::bar",
        name="bar",
        file_path="m.py",
        language="python",
        body=(IRStmt(kind="STATEMENT", label="x", line=1),),
    )
    cfgs = {
        "m.py::foo": build_cfg_from_ir(ir_foo, max_nodes=100),
        "m.py::bar": build_cfg_from_ir(ir_bar, max_nodes=100),
    }
    orig_n = len(cfgs["m.py::foo"].nodes)
    exp = expand_cfg_calls(cfgs["m.py::foo"], cfgs, max_call_depth=2, inline_calls=True)
    assert len(exp.nodes) > orig_n
    assert any(n.id.startswith("inl") for n in exp.nodes.values())


def test_expand_cfg_calls_marks_mutual_recursion() -> None:
    ir_a = IRMethod(
        symbol_id="m.py::a",
        name="a",
        file_path="m.py",
        language="python",
        body=(IRStmt(kind="CALL", target="b", line=1),),
    )
    ir_b = IRMethod(
        symbol_id="m.py::b",
        name="b",
        file_path="m.py",
        language="python",
        body=(IRStmt(kind="CALL", target="a", line=1),),
    )
    cfgs = {
        "m.py::a": build_cfg_from_ir(ir_a, max_nodes=100),
        "m.py::b": build_cfg_from_ir(ir_b, max_nodes=100),
    }
    expanded = expand_cfg_calls(cfgs["m.py::a"], cfgs, max_call_depth=5, inline_calls=True)
    labels = [n.label for n in expanded.nodes.values() if n.kind == "CALL"]
    assert any("(recursive)" in lbl for lbl in labels)


def test_run_scan_emit_cfg_writes_sidecars(tmp_path: Path) -> None:
    root = tmp_path / "proj2"
    root.mkdir()
    p = root / "one.py"
    p.write_text(
        "def entry():\n"
        "    if True:\n"
        "        pass\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        languages="python",
        entry=["one.py::entry"],
        emit_cfg=True,
        business_rules=False,
    )
    run_scan(cfg)
    slug_dir = next(d for d in out.iterdir() if d.is_dir() and (d / "cfg.json").exists())
    assert (slug_dir / "cfg.json").is_file()
    assert (slug_dir / "cfg.mmd").is_file()
    assert (slug_dir / "cfg-paths.md").is_file()
    assert (slug_dir / "cfg-paths.mmd").is_file()
    flow = (slug_dir / "flow.md").read_text(encoding="utf-8")
    assert "Control-flow graph" in flow
    assert "Execution paths" in flow


def test_run_scan_emit_cfg_inline_calls(tmp_path: Path) -> None:
    root = tmp_path / "proj3"
    root.mkdir()
    (root / "two.py").write_text(
        "def foo():\n"
        "    bar()\n"
        "def bar():\n"
        "    pass\n",
        encoding="utf-8",
    )
    out = tmp_path / "out3"
    cfg = ScanConfig(
        project_root=root,
        output_path=out,
        formats=("md",),
        languages="python",
        entry=["two.py::foo"],
        emit_cfg=True,
        cfg_inline_calls=True,
        cfg_call_depth=2,
        business_rules=False,
    )
    run_scan(cfg)
    slug_dir = next(d for d in out.iterdir() if d.is_dir() and (d / "cfg.json").exists())
    data = (slug_dir / "cfg.json").read_text(encoding="utf-8")
    assert "inl" in data
