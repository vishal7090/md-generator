from __future__ import annotations

import subprocess
from pathlib import Path

import networkx as nx
import pytest

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.diff_analysis import (
    DiffAnalysisError,
    build_pr_impact_payload,
    diff_impact_nodes,
    git_changed_files,
    nodes_touching_files,
)
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph
from md_generator.codeflow.runtime.python_edge_counter import PythonEdgeCounter, trace_from_pairs


def test_git_changed_files_requires_git_dir(tmp_path: Path) -> None:
    nogit = tmp_path / "plain"
    nogit.mkdir()
    with pytest.raises(DiffAnalysisError):
        git_changed_files(nogit, "main", "main")


def test_git_changed_files_name_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.st"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.py").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "c1"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "topic"], cwd=repo, check=True, capture_output=True)
    (repo / "a.py").write_text("v2\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "c2"], cwd=repo, check=True, capture_output=True)
    files = git_changed_files(repo, "HEAD~1", "HEAD")
    assert "a.py" in files


def test_diff_impact_includes_downstream() -> None:
    g: CodeflowGraph = nx.MultiDiGraph()
    for nid, fp in [("a.py::f", "a.py"), ("a.py::g", "a.py"), ("b.py::h", "b.py")]:
        g.add_node(nid, file_path=fp, type="method")
    g.add_edge("a.py::f", "a.py::g", key=0, relation=rel.REL_CALLS)
    g.add_edge("a.py::g", "b.py::h", key=0, relation=rel.REL_CALLS)
    seeds = nodes_touching_files(g, {"a.py"}, primary_repo_label=None)
    assert seeds == {"a.py::f", "a.py::g"}
    imp = diff_impact_nodes(g, seeds)
    assert "b.py::h" in imp


def test_build_pr_impact_payload_counts() -> None:
    g: CodeflowGraph = nx.MultiDiGraph()
    g.add_node("a.py::f", file_path="a.py", type="method")
    g.add_node("a.py::g", file_path="a.py", type="method")
    g.add_edge("a.py::f", "a.py::g", key=0, relation=rel.REL_CALLS)
    p = build_pr_impact_payload(g, base="main", head="topic", changed_files=["a.py"])
    assert p["seed_nodes_count"] == 2
    assert p["impacted_nodes_count"] == 2


def test_python_edge_counter_json_keys() -> None:
    c = PythonEdgeCounter()
    c.record("START_1", "N2", 3.0)
    d = c.to_trace_dict()
    assert d["counts"]["START_1->N2"] == 3.0
    d2 = trace_from_pairs([("A", "B"), ("B", "C")], [1.0, 2.0])
    assert d2["counts"]["A->B"] == 1.0
    assert d2["counts"]["B->C"] == 2.0
