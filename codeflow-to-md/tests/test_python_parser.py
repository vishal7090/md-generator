from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.parsers.python_parser import PythonParser


def test_python_parser_resolves_self_calls(tmp_path: Path) -> None:
    p = tmp_path / "m.py"
    p.write_text(
        """
class A:
    def a(self):
        self.b()
    def b(self):
        pass
""",
        encoding="utf-8",
    )
    fr = PythonParser().parse_file(p, tmp_path)
    ids = set(fr.symbol_ids)
    assert any("A.a" in x for x in ids)
    assert any("A.b" in x for x in ids)
    assert any(c.caller_id.endswith("A.a") and "A.b" in c.callee_hint for c in fr.calls)
