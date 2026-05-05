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
    assert fr.ir_dump is not None
    assert int(fr.ir_dump.get("irVersion", 0)) >= 1  # type: ignore[arg-type]
    funcs = fr.ir_dump.get("funcs") or []
    main_fn = next((f for f in funcs if str(f.get("id", "")).endswith("::A")), None)
    assert main_fn is not None
    body = main_fn.get("body") or []
    assert isinstance(body, list) and len(body) >= 1
