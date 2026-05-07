from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.graph.builder import build_graph
from md_generator.codeflow.graph.dependency_builder import file_import_successors
from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.parsers.python_parser import PythonParser
from md_generator.codeflow.parsers.unified_parser import parse_source_file
from md_generator.codeflow.parsers.base import ParserRegistry, register_defaults


def test_python_parser_emits_import_structural_edges(tmp_path: Path) -> None:
    p = tmp_path / "m.py"
    p.write_text("import os\nfrom collections import abc\n", encoding="utf-8")
    fr = PythonParser().parse_file(p, tmp_path)
    imp = [e for e in fr.structural_edges if e.relation == rel.REL_IMPORTS]
    assert len(imp) >= 2
    targets = {e.target_id for e in imp}
    assert any("os" in t for t in targets)


def test_apply_import_resolution_python_package(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text("X = 1\n", encoding="utf-8")
    main = tmp_path / "main.py"
    main.write_text("import pkg.mod\n", encoding="utf-8")
    results: list[FileParseResult] = []
    for path in (main, pkg / "__init__.py", pkg / "mod.py"):
        results.append(PythonParser().parse_file(path, tmp_path))
    g = build_graph(results, tmp_path, include_structural=True, include_references=False).graph
    succ = file_import_successors(g, "file:main.py")
    assert any("pkg/mod.py" in s for s in succ)


def test_unified_parser_cpp_treesitter_mode_returns_result(tmp_path: Path) -> None:
    p = tmp_path / "a.cpp"
    p.write_text("int main(){ return 0; }\n", encoding="utf-8")
    reg = ParserRegistry()
    register_defaults(reg)
    fr = parse_source_file(reg, p, tmp_path, "cpp", "treesitter")
    assert fr is not None
    # Tree-sitter may be absent in minimal env; then empty is ok
    assert isinstance(fr.symbol_ids, list)
