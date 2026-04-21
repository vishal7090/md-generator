from __future__ import annotations

from md_generator.db.core.erd.model import FKEdge, TableKey


def _mermaid_escape_label(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _fk_edge_label(edge: FKEdge) -> str:
    pairs = list(zip(edge.constrained_columns, edge.referred_columns))
    if pairs:
        return ", ".join(f"{a}->{b}" for a, b in pairs)
    return edge.fk_name or "FK"


def build_mermaid_er(graph_title: str, nodes: frozenset[TableKey], edges: tuple[FKEdge, ...]) -> str:
    """
    Deterministic Mermaid ``erDiagram`` source (relationships only).
    Entity ids are ``E0``, ``E1``, … in sorted ``(schema, table)`` order.
    """
    sorted_nodes = sorted(nodes)
    id_for: dict[TableKey, str] = {k: f"E{i}" for i, k in enumerate(sorted_nodes)}
    lines = ["erDiagram", f"  %% {_mermaid_escape_label(graph_title)}"]
    for e in edges:
        child = id_for.get(e.from_key)
        parent = id_for.get(e.to_key)
        if not child or not parent:
            continue
        lbl = _mermaid_escape_label(_fk_edge_label(e))
        lines.append(f'  {parent} ||--o{{ {child} : "{lbl}"')
    lines.append("")
    return "\n".join(lines) + "\n"


def mermaid_bundle_markdown(title: str, diagram: str) -> str:
    """Markdown file with a fenced Mermaid block (e.g. for GitHub preview)."""
    t = _mermaid_escape_label(title).strip() or "ER diagram"
    return f"# {t}\n\n```mermaid\n{diagram.rstrip()}\n```\n"
