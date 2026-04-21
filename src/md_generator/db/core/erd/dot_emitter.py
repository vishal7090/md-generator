from __future__ import annotations

from md_generator.db.core.erd.model import FKEdge, TableKey


def escape_dot_label(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )


def _node_display_name(key: TableKey) -> str:
    return f"{key[0]}.{key[1]}"


def _edge_label(edge: FKEdge) -> str:
    pairs = list(zip(edge.constrained_columns, edge.referred_columns))
    if pairs:
        return ", ".join(f"{a}->{b}" for a, b in pairs)
    return edge.fk_name or "FK"


def build_dot(graph_title: str, nodes: frozenset[TableKey], edges: tuple[FKEdge, ...]) -> str:
    """Deterministic DOT document."""
    sorted_nodes = sorted(nodes)
    node_ids = {k: f"n{i}" for i, k in enumerate(sorted_nodes)}
    lines = [
        f'digraph "{escape_dot_label(graph_title)}" {{',
        "  graph [ordering=out, rankdir=LR];",
        '  node [shape=box, style=rounded, fontname="Helvetica"];',
        '  edge [fontname="Helvetica", fontsize=10];',
    ]
    for k in sorted_nodes:
        nid = node_ids[k]
        lbl = escape_dot_label(_node_display_name(k))
        lines.append(f'  {nid} [label="{lbl}"];')
    for e in edges:
        fe = node_ids.get(e.from_key)
        te = node_ids.get(e.to_key)
        if not fe or not te:
            continue
        el = escape_dot_label(_edge_label(e))
        lines.append(f'  {fe} -> {te} [label="{el}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"
