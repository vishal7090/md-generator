"""Graph-native clustering (modularity) on the file-level import layer."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph import relations as rel


def file_import_digraph(g: nx.DiGraph) -> nx.DiGraph:
    """Subgraph of ``file:`` nodes linked by ``IMPORTS`` edges only."""
    fg = nx.DiGraph()
    for n in g.nodes():
        if isinstance(n, str) and n.startswith("file:"):
            fg.add_node(n, **dict(g.nodes[n]))
    for u, v, d in g.edges(data=True):
        if d.get("relation") != rel.REL_IMPORTS:
            continue
        if isinstance(u, str) and u.startswith("file:") and isinstance(v, str) and v.startswith("file:"):
            fg.add_edge(u, v, **dict(d))
    return fg


def greedy_modularity_file_communities(
    g: nx.DiGraph,
    *,
    max_undirected_nodes: int = 4000,
) -> list[list[str]]:
    """Run ``greedy_modularity_communities`` on an undirected view of the file import graph."""
    fg = file_import_digraph(g)
    if fg.number_of_nodes() == 0:
        return []
    ug = nx.Graph()
    ug.add_nodes_from(fg.nodes())
    for u, v in fg.edges():
        ug.add_edge(u, v)
    if ug.number_of_nodes() > max_undirected_nodes:
        ranked = sorted(ug.nodes(), key=lambda n: ug.degree(n), reverse=True)
        keep = set(ranked[:max_undirected_nodes])
        ug = ug.subgraph(keep).copy()
    comms = nx.community.greedy_modularity_communities(ug)
    return [sorted(c) for c in comms]
