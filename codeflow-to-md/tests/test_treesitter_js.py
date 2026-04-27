from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_javascript")

from pathlib import Path

from tree_sitter import Language

import tree_sitter_javascript as tsjs

from md_generator.codeflow.parsers.treesitter_js_ts_parser import TreesitterJsTsParser


def test_treesitter_finds_call(tmp_path: Path) -> None:
    p = tmp_path / "a.js"
    p.write_text(
        """
function outer() {
  function inner() {
    foo();
  }
  inner();
}
""",
        encoding="utf-8",
    )
    lang = Language(tsjs.language())
    fr = TreesitterJsTsParser("javascript", lang).parse_file(p, tmp_path)
    assert any("foo" in c.callee_hint for c in fr.calls)
    assert any("inner" in c.callee_hint for c in fr.calls)
