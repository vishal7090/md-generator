from __future__ import annotations

from md_generator.db.core.erd.model import FKEdge, TableKey, collect_fk_edges, table_key
from md_generator.db.core.models import TableDetail


def sorted_details(details: list[TableDetail]) -> list[TableDetail]:
    return sorted(details, key=table_key)


def capped_nodes(details_sorted: list[TableDetail], max_tables: int) -> frozenset[TableKey]:
    if not details_sorted:
        return frozenset()
    n = max(1, min(max_tables, len(details_sorted)))
    return frozenset(table_key(d) for d in details_sorted[:n])


def edges_induced(edges: tuple[FKEdge, ...], nodes: frozenset[TableKey]) -> tuple[FKEdge, ...]:
    return tuple(e for e in edges if e.from_key in nodes and e.to_key in nodes)


def subgraph_full(details: list[TableDetail], max_tables: int) -> tuple[frozenset[TableKey], tuple[FKEdge, ...]]:
    ds = sorted_details(details)
    edges = collect_fk_edges(details)
    nodes = capped_nodes(ds, max_tables)
    return nodes, edges_induced(edges, nodes)


def subgraphs_per_schema(
    details: list[TableDetail], max_tables: int
) -> list[tuple[str, frozenset[TableKey], tuple[FKEdge, ...]]]:
    """One subgraph per schema present in the capped universe."""
    ds = sorted_details(details)
    nodes_s = capped_nodes(ds, max_tables)
    all_edges = collect_fk_edges(details)
    sch_to: dict[str, set[TableKey]] = {}
    for k in sorted(nodes_s):
        sch_to.setdefault(k[0], set()).add(k)
    out: list[tuple[str, frozenset[TableKey], tuple[FKEdge, ...]]] = []
    for sch in sorted(sch_to.keys()):
        ns = frozenset(sch_to[sch])
        out.append((sch, ns, edges_induced(all_edges, ns)))
    return out


def subgraphs_per_table(
    details: list[TableDetail], max_tables: int
) -> list[tuple[str, frozenset[TableKey], tuple[FKEdge, ...]]]:
    """Ego graph per center table (first max_tables centers), neighbors from full FK edge set."""
    ds = sorted_details(details)
    all_edges = collect_fk_edges(details)
    ncent = max(1, min(max_tables, len(ds)))
    centers = [table_key(d) for d in ds[:ncent]]
    out: list[tuple[str, frozenset[TableKey], tuple[FKEdge, ...]]] = []
    for ck in centers:
        nodes: set[TableKey] = {ck}
        for e in all_edges:
            if e.from_key == ck:
                nodes.add(e.to_key)
            if e.to_key == ck:
                nodes.add(e.from_key)
        ns = frozenset(nodes)
        slug = f"{ck[0]}_{ck[1]}"
        out.append((slug, ns, edges_induced(all_edges, ns)))
    return out
