from __future__ import annotations

from pathlib import Path

import networkx as nx

from md_generator.graph.core.extractor import extract_to_markdown
from md_generator.graph.core.run_config import GraphRunConfig


def test_extract_graphml_writes_readme(tmp_path: Path) -> None:
    g = nx.DiGraph()
    g.add_node("a", label="User", name="Ann")
    g.add_node("b", label="Order")
    g.add_edge("a", "b", type="PLACED")
    graph_path = tmp_path / "sample.graphml"
    nx.write_graphml(g, graph_path)
    out = tmp_path / "out"
    cfg = GraphRunConfig(
        source="networkx",
        graph_file=graph_path,
        output_path=out,
        max_nodes=100,
        max_edges=100,
    ).normalized()
    extract_to_markdown(cfg)
    assert (out / "README.md").is_file()
    assert (out / "graph_summary.md").is_file()
    assert "## All nodes" in (out / "graph_summary.md").read_text(encoding="utf-8")
    assert (out / "nodes.md").is_file()
    assert (out / "relationship.md").is_file()


def test_extract_graphml_individual_layout(tmp_path: Path) -> None:
    g = nx.Graph()
    g.add_node("x", label="N")
    g.add_node("y", label="N")
    g.add_edge("x", "y", type="R")
    graph_path = tmp_path / "t.graphml"
    nx.write_graphml(g, graph_path)
    out = tmp_path / "out_ind"
    cfg = GraphRunConfig(
        source="networkx",
        graph_file=graph_path,
        output_path=out,
        combine_markdown=False,
        max_nodes=100,
        max_edges=100,
    ).normalized()
    extract_to_markdown(cfg)
    assert (out / "nodes" / "node_x.md").is_file()
    assert (out / "relationships").is_dir()
    summary = (out / "graph_summary.md").read_text(encoding="utf-8")
    assert "## All nodes" not in summary
