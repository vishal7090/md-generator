from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.graph.builder import build_graph
from md_generator.codeflow.graph.diff_analysis import nodes_touching_files
from md_generator.codeflow.graph.multi_repo import merge_graphs, repo_label
from md_generator.codeflow.models.ir import FileParseResult


def test_repo_label_unique() -> None:
    used: set[str] = set()
    a = repo_label(Path("/x/foo"), 0, used)
    b = repo_label(Path("/y/foo"), 1, used)
    assert a != b
    assert "foo" in (a, b) or a.startswith("foo")


def test_merge_graphs_same_relative_paths_distinct_ids(tmp_path: Path) -> None:
    r1 = tmp_path / "repo_one"
    r2 = tmp_path / "repo_two"
    (r1 / "src").mkdir(parents=True)
    (r2 / "src").mkdir(parents=True)
    fr1 = FileParseResult(path=r1 / "src" / "m.py", language="python")
    fr1.symbol_ids = ["src/m.py::f"]
    fr2 = FileParseResult(path=r2 / "src" / "m.py", language="python")
    fr2.symbol_ids = ["src/m.py::f"]
    g1 = build_graph([fr1], r1).graph
    g2 = build_graph([fr2], r2).graph
    e1, e2 = g1.number_of_edges(), g2.number_of_edges()
    m = merge_graphs([g1, g2], ["aa", "bb"])
    nodes = list(m.nodes())
    assert len(nodes) == len(set(nodes))
    assert any(str(n).startswith("aa::") for n in nodes)
    assert any(str(n).startswith("bb::") for n in nodes)
    assert m.number_of_edges() == e1 + e2
    assert m.nodes["aa::src/m.py::f"].get("repo") == "aa"
    assert m.nodes["bb::src/m.py::f"].get("repo") == "bb"


def test_nodes_touching_files_primary_repo_only() -> None:
    import networkx as nx

    from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph

    g: CodeflowGraph = nx.MultiDiGraph()
    g.add_node("p::a.py::f", file_path="a.py", repo="p")
    g.add_node("q::a.py::f", file_path="a.py", repo="q")
    s = nodes_touching_files(g, {"a.py"}, primary_repo_label="p")
    assert s == {"p::a.py::f"}
