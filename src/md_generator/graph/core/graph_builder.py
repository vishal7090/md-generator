from __future__ import annotations

from collections import defaultdict, deque

from md_generator.graph.core.models import GraphMetadata, Node, Relationship


def _node_by_id(nodes: tuple[Node, ...]) -> dict[str, Node]:
    return {n.id: n for n in nodes}


def apply_caps_sorted(meta: GraphMetadata, *, max_nodes: int, max_edges: int) -> GraphMetadata:
    """Truncate to max counts with stable ordering."""
    snodes = sorted(meta.nodes, key=lambda n: n.id)[:max_nodes]
    allowed = {n.id for n in snodes}
    srels = [r for r in sorted(meta.relationships, key=lambda r: (r.type, r.id, r.start_node, r.end_node)) if r.start_node in allowed and r.end_node in allowed][:max_edges]
    return GraphMetadata(nodes=tuple(snodes), relationships=tuple(srels))


def bfs_subgraph(
    meta: GraphMetadata,
    start_node: str,
    depth: int,
    *,
    max_nodes: int,
    max_edges: int,
) -> GraphMetadata:
    """Undirected BFS from start_node; depth 0 means start only; unlimited use large depth."""
    ids = _node_by_id(meta.nodes)
    if start_node not in ids:
        return GraphMetadata(nodes=tuple(), relationships=tuple())

    if depth <= 0:
        depth = 10**9

    adj: dict[str, list[str]] = defaultdict(list)
    for r in meta.relationships:
        adj[r.start_node].append(r.end_node)
        adj[r.end_node].append(r.start_node)

    q: deque[tuple[str, int]] = deque([(start_node, 0)])
    visited_depth: dict[str, int] = {start_node: 0}
    while q:
        nid, d = q.popleft()
        if d >= depth:
            continue
        if len(visited_depth) >= max_nodes:
            break
        for nb in sorted(adj[nid]):
            if nb in visited_depth:
                continue
            if len(visited_depth) >= max_nodes:
                break
            visited_depth[nb] = d + 1
            q.append((nb, d + 1))

    allowed = frozenset(visited_depth.keys())
    cand_rels = [
        r
        for r in sorted(meta.relationships, key=lambda x: (x.type, x.id, x.start_node, x.end_node))
        if r.start_node in allowed and r.end_node in allowed
    ]
    rels = cand_rels[:max_edges]
    node_ids = allowed
    nodes = tuple(sorted((ids[i] for i in node_ids if i in ids), key=lambda n: n.id))
    return GraphMetadata(nodes=nodes, relationships=tuple(rels))


def normalize_metadata(meta: GraphMetadata, *, start_node: str | None, depth: int, max_nodes: int, max_edges: int) -> GraphMetadata:
    if start_node:
        return bfs_subgraph(meta, start_node, depth, max_nodes=max_nodes, max_edges=max_edges)
    return apply_caps_sorted(meta, max_nodes=max_nodes, max_edges=max_edges)
