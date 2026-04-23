from __future__ import annotations

from md_generator.graph.core.graph_builder import apply_caps_sorted, bfs_subgraph, normalize_metadata
from md_generator.graph.core.models import GraphMetadata, Node, Relationship


def _triangle() -> GraphMetadata:
    nodes = (
        Node("a", ("N",), {}),
        Node("b", ("N",), {}),
        Node("c", ("N",), {}),
    )
    rels = (
        Relationship("r1", "R", "a", "b", {}),
        Relationship("r2", "R", "b", "c", {}),
        Relationship("r3", "R", "a", "c", {}),
    )
    return GraphMetadata(nodes=nodes, relationships=rels)


def test_bfs_subgraph_depth() -> None:
    m = _triangle()
    out = bfs_subgraph(m, "a", 1, max_nodes=100, max_edges=100)
    ids = {n.id for n in out.nodes}
    assert ids == {"a", "b", "c"}  # triangle: all neighbors of a are b,c at dist 1


def test_apply_caps_sorted() -> None:
    m = GraphMetadata(
        nodes=tuple(Node(str(i), ("X",), {}) for i in range(5)),
        relationships=tuple(),
    )
    out = apply_caps_sorted(m, max_nodes=3, max_edges=10)
    assert len(out.nodes) == 3


def test_normalize_metadata_no_start() -> None:
    m = GraphMetadata(
        nodes=tuple(Node(str(i), (), {}) for i in range(10)),
        relationships=tuple(),
    )
    out = normalize_metadata(m, start_node=None, depth=0, max_nodes=3, max_edges=5)
    assert len(out.nodes) == 3
