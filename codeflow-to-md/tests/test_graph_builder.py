from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.graph.builder import build_graph, graph_to_serializable
from md_generator.codeflow.models.ir import CallSite, FileParseResult


def test_build_graph_merge(tmp_path: Path) -> None:
    fr = FileParseResult(path=tmp_path / "a.py", language="python")
    fr.symbol_ids = ["a.py::f"]
    fr.calls = [
        CallSite(
            caller_id="a.py::f",
            callee_hint="a.py::g",
            resolution="static",
            is_async=False,
            line=1,
        )
    ]
    r = build_graph([fr], tmp_path)
    ser = graph_to_serializable(r.graph)
    assert any(n["id"] == "a.py::f" for n in ser["nodes"])
