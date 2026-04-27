from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from md_generator.codeflow.parsers.go_parser import GoParser


@pytest.mark.skipif(shutil.which("go") is None, reason="go not on PATH")
def test_go_parser_smoke(tmp_path: Path) -> None:
    p = tmp_path / "x.go"
    p.write_text(
        """package x
func A() { B() }
func B() {}
""",
        encoding="utf-8",
    )
    fr = GoParser().parse_file(p, tmp_path)
    assert any("B" in c.callee_hint for c in fr.calls)
