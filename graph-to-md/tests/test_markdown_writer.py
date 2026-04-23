from __future__ import annotations

from md_generator.graph.core.markdown_writer import (
    format_graph_summary,
    format_graph_summary_with_embedded_documents,
    format_node_markdown,
    format_relationship_markdown,
    slugify_segment,
)
from md_generator.graph.core.models import GraphMetadata, Node, Relationship


def test_slugify_segment() -> None:
    assert slugify_segment("a:b/c") == "a_b_c"


def test_format_node_markdown() -> None:
    n1 = Node("1", ("User",), {"name": "Ann"})
    n2 = Node("22", ("Order",), {})
    r = Relationship("r1", "PLACED", "1", "22", {})
    meta = GraphMetadata(nodes=(n1, n2), relationships=(r,))
    md = format_node_markdown(n1, meta)
    assert "# Node: 1" in md
    assert "* User" in md
    assert "| name | Ann |" in md
    assert "[:PLACED]->" in md


def test_format_relationship_markdown() -> None:
    n1 = Node("1", ("User",), {})
    n2 = Node("22", ("Order",), {})
    r = Relationship("r1", "PLACED", "1", "22", {"when": "2024"})
    meta = GraphMetadata(nodes=(n1, n2), relationships=(r,))
    md = format_relationship_markdown(r, meta)
    assert "# Relationship: PLACED" in md
    assert "User (id: 1)" in md
    assert "Order (id: 22)" in md
    assert "| when | 2024 |" in md


def test_format_graph_summary_with_embedded() -> None:
    n1 = Node("1", ("User",), {})
    n2 = Node("22", ("Order",), {})
    r = Relationship("r1", "PLACED", "1", "22", {})
    meta = GraphMetadata(nodes=(n1, n2), relationships=(r,))
    md = format_graph_summary_with_embedded_documents(meta)
    assert "## All nodes" in md
    assert "## All relationships" in md
    assert "# Node: 1" in md
    assert "# Relationship: PLACED" in md


def test_format_graph_summary() -> None:
    meta = GraphMetadata(
        nodes=(Node("a", ("L",), {}), Node("b", ("L",), {})),
        relationships=(Relationship("1", "KNOWS", "a", "b", {}),),
    )
    md = format_graph_summary(meta)
    assert "## Nodes Count" in md
    assert "2" in md
    assert "* KNOWS" in md
    assert "## Labels" in md
