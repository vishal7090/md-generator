from __future__ import annotations

from pathlib import Path

import networkx as nx

from md_generator.graph.core.extractor import extract_to_markdown
from md_generator.graph.core.run_config import GraphRunConfig, VizConfig
from md_generator.graph.core.viz import metadata_to_mermaid_body, write_graph_mermaid


def test_metadata_to_mermaid_body() -> None:
    from md_generator.graph.core.models import GraphMetadata, Node, Relationship

    meta = GraphMetadata(
        nodes=(Node("a", ("User",), {}), Node("b", ("Order",), {})),
        relationships=(Relationship("r1", "PLACED", "a", "b", {}),),
    )
    body = metadata_to_mermaid_body(meta)
    assert "flowchart LR" in body
    assert "-->|" in body or "-->" in body
    assert "PLACED" in body


def test_extract_writes_graph_mmd(tmp_path: Path) -> None:
    g = nx.DiGraph()
    g.add_node("a", label="U")
    g.add_node("b", label="O")
    g.add_edge("a", "b", type="R")
    gf = tmp_path / "g.graphml"
    nx.write_graphml(g, gf)
    out = tmp_path / "out"
    cfg = GraphRunConfig(
        source="networkx",
        graph_file=gf,
        output_path=out,
        viz=VizConfig(enabled=False, mermaid=True),
        max_nodes=50,
        max_edges=50,
    ).normalized()
    extract_to_markdown(cfg)
    assert (out / "graph" / "graph.mmd").is_file()
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "```mermaid" in readme
    assert "flowchart LR" in readme


def test_write_graph_mermaid_returns_body(tmp_path: Path) -> None:
    from md_generator.graph.core.models import GraphMetadata, Node

    meta = GraphMetadata(nodes=(Node("x", ("N",), {}),), relationships=tuple())
    body = write_graph_mermaid(meta, tmp_path)
    assert "flowchart LR" in body
    assert (tmp_path / "graph" / "graph.mmd").read_text(encoding="utf-8").strip().startswith("flowchart")
