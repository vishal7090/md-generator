from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx


@dataclass(slots=True)
class FlowSlice:
    entry_id: str
    nodes: set[str]
    edges: list[tuple[str, str, dict]]
    depth: int
    cycle_nodes: set[str] = field(default_factory=set)
    truncated: bool = False


def walk_with_depth(
    g: nx.DiGraph,
    start: str,
    max_depth: int,
) -> tuple[set[str], list[tuple[str, str, dict]], set[str], bool]:
    """Reachability from start within ``max_depth`` hops (shortest-path layering)."""
    if start not in g:
        return {start}, [], set(), False
    try:
        plen = nx.single_source_shortest_path_length(g, start, cutoff=max_depth)
    except nx.NetworkXError:
        plen = {start: 0}

    nodes = set(plen.keys())
    edges_out: list[tuple[str, str, dict]] = []
    cycle_guess: set[str] = set()
    truncated = False

    for u in nodes:
        du = plen[u]
        if du >= max_depth:
            succ = list(g.successors(u))
            if succ:
                truncated = True
            continue
        for v in g.successors(u):
            ed = dict(g.edges[u, v])
            edges_out.append((u, v, ed))
            dv = plen.get(v)
            if dv is not None and dv <= du:
                cycle_guess.add(v)
            if v not in plen and du + 1 > max_depth:
                truncated = True

    return nodes, edges_out, cycle_guess, truncated


def slice_from_entry(
    g: nx.DiGraph,
    entry_id: str,
    max_depth: int,
) -> FlowSlice:
    nodes, edges, cycles, truncated = walk_with_depth(g, entry_id, max_depth)
    return FlowSlice(
        entry_id=entry_id,
        nodes=nodes,
        edges=edges,
        depth=max_depth,
        cycle_nodes=cycles,
        truncated=truncated,
    )
