from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.graph.builder import build_graph, graph_to_serializable
from md_generator.codeflow.graph.enricher import called_by_direct, impact_descendants
from md_generator.codeflow.graph.export_schema import to_stable_schema
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
        ),
        CallSite(
            caller_id="a.py::f",
            callee_hint="a.py::f",
            resolution="static",
            is_async=False,
            line=2,
        ),
        CallSite(
            caller_id="a.py::f",
            callee_hint="unknown::dyn",
            resolution="dynamic",
            is_async=False,
            line=3,
        ),
    ]
    r = build_graph([fr], tmp_path)
    ser = graph_to_serializable(r.graph)
    assert any(n["id"] == "a.py::f" for n in ser["nodes"])
    edges = ser["edges"]
    e_fg = next(x for x in edges if x["source"] == "a.py::f" and x["target"] == "a.py::g")
    assert e_fg.get("unknown_call") is False
    assert e_fg.get("recursive") is False
    assert e_fg.get("relation") == "CALLS"
    assert e_fg.get("confidence") == 1.0
    e_ff = next(x for x in edges if x["source"] == "a.py::f" and x["target"] == "a.py::f")
    assert e_ff.get("recursive") is True
    assert e_ff.get("unknown_call") is False
    e_fun = next(x for x in edges if x["target"] == "unknown::dyn")
    assert e_fun.get("unknown_call") is True
    assert e_fun.get("confidence") == 0.5


def test_enricher_called_by_and_impact(tmp_path: Path) -> None:
    fr = FileParseResult(path=tmp_path / "a.py", language="python")
    fr.symbol_ids = ["a.py::main", "a.py::g"]
    fr.calls = [
        CallSite(
            caller_id="a.py::main",
            callee_hint="a.py::g",
            resolution="static",
            is_async=False,
            line=1,
        ),
    ]
    g = build_graph([fr], tmp_path).graph
    assert called_by_direct(g, "a.py::g", 10) == ["a.py::main"]
    assert impact_descendants(g, "a.py::main", 10) == ["a.py::g"]


def test_to_stable_schema_contains_file_and_calls(tmp_path: Path) -> None:
    fr = FileParseResult(path=tmp_path / "x.py", language="python")
    fr.symbol_ids = ["x.py::C.m"]
    fr.calls = [
        CallSite(
            caller_id="x.py::C.m",
            callee_hint="x.py::C.n",
            resolution="static",
            is_async=False,
            line=3,
        ),
    ]
    g = build_graph([fr], tmp_path).graph
    sch = to_stable_schema(g)
    kinds = {n["kind"] for n in sch["nodes"]}
    assert "File" in kinds
    assert "Class" in kinds
    call_edges = [e for e in sch["edges"] if e.get("kind") == "CALLS"]
    assert len(call_edges) >= 1
