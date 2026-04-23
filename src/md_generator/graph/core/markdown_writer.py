from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from md_generator.graph.core.models import GraphMetadata, Node, Relationship


def slugify_segment(name: str, max_len: int = 120) -> str:
    s = str(name).strip()
    s = re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE)
    s = s.strip("._") or "unnamed"
    if len(s) > max_len:
        s = s[:max_len].rstrip("._")
    return s or "unnamed"


def _md_escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _format_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list, tuple)):
        try:
            return json.dumps(v, sort_keys=True, ensure_ascii=False)
        except TypeError:
            return str(v)
    return str(v)


def _props_table(props: dict[str, Any]) -> str:
    if not props:
        return "_No properties._\n"
    lines = [
        "| Key | Value |",
        "| --- | ----- |",
    ]
    for k in sorted(props.keys()):
        lines.append(f"| {_md_escape_cell(str(k))} | {_md_escape_cell(_format_value(props[k]))} |")
    return "\n".join(lines) + "\n"


def _node_labels_md(labels: tuple[str, ...]) -> str:
    if not labels:
        return "_No labels._\n"
    return "\n".join(f"* {lab}" for lab in labels) + "\n"


def _incident_rels_lines(nid: str, meta: GraphMetadata) -> list[str]:
    incident: list[Relationship] = []
    for r in meta.relationships:
        if r.start_node == nid or r.end_node == nid:
            incident.append(r)
    lines: list[str] = []
    for r in sorted(incident, key=lambda x: (x.type, x.id, x.start_node, x.end_node)):
        a = _label_hint(meta, r.start_node)
        b = _label_hint(meta, r.end_node)
        lines.append(f"* ({a})-[:{r.type}]->({b})")
    return lines


def _label_hint(meta: GraphMetadata, node_id: str) -> str:
    for n in meta.nodes:
        if n.id == node_id:
            if n.labels:
                return n.labels_sorted()[0]
            return "Node"
    return "Node"


def format_node_markdown(n: Node, meta: GraphMetadata) -> str:
    rel_lines = _incident_rels_lines(n.id, meta)
    rel_section = "\n".join(rel_lines) + "\n" if rel_lines else "_No relationships._\n"
    parts = [
        f"# Node: {n.id}",
        "",
        "## Labels",
        "",
        _node_labels_md(n.labels_sorted()),
        "## Properties",
        "",
        _props_table(dict(n.properties)),
        "## Relationships",
        "",
        rel_section,
    ]
    return "\n".join(parts).rstrip() + "\n"


def format_relationship_markdown(r: Relationship, meta: GraphMetadata) -> str:
    def node_line(nid: str) -> str:
        for n in meta.nodes:
            if n.id == nid:
                lab = n.labels_sorted()[0] if n.labels else "Node"
                return f"{lab} (id: {nid})"
        return f"Node (id: {nid})"

    parts = [
        f"# Relationship: {r.type}",
        "",
        "## From",
        "",
        node_line(r.start_node),
        "",
        "## To",
        "",
        node_line(r.end_node),
        "",
        "## Properties",
        "",
        _props_table(dict(r.properties)),
    ]
    return "\n".join(parts).rstrip() + "\n"


def format_graph_summary(meta: GraphMetadata) -> str:
    rel_types = sorted({r.type for r in meta.relationships})
    label_counts: dict[str, int] = defaultdict(int)
    for n in meta.nodes:
        for lab in n.labels:
            label_counts[lab] += 1
    label_lines = "\n".join(f"* {k}: {label_counts[k]}" for k in sorted(label_counts)) or "_None_"

    parts = [
        "# Graph Summary",
        "",
        "## Nodes Count",
        "",
        str(len(meta.nodes)),
        "",
        "## Relationships Count",
        "",
        str(len(meta.relationships)),
        "",
        "## Relationship Types",
        "",
    ]
    if rel_types:
        parts.append("\n".join(f"* {t}" for t in rel_types))
    else:
        parts.append("_None_")
    parts.extend(
        [
            "",
            "## Labels (nodes)",
            "",
            label_lines + "\n",
        ]
    )
    return "\n".join(parts).rstrip() + "\n"


def format_combined_nodes_document(meta: GraphMetadata) -> str:
    blocks = [format_node_markdown(n, meta) for n in sorted(meta.nodes, key=lambda n: n.id)]
    return "# Nodes\n\n" + "\n\n---\n\n".join(blocks).rstrip() + "\n"


def format_combined_relationships_document(meta: GraphMetadata) -> str:
    blocks = [
        format_relationship_markdown(r, meta)
        for r in sorted(meta.relationships, key=lambda r: (r.type, r.id, r.start_node, r.end_node))
    ]
    return "# Relationships\n\n" + "\n\n---\n\n".join(blocks).rstrip() + "\n"


def format_graph_summary_with_embedded_documents(meta: GraphMetadata) -> str:
    """Summary stats plus full combined nodes and relationships (for LLM-ready single file)."""
    summary = format_graph_summary(meta).rstrip()
    nodes_doc = format_combined_nodes_document(meta).rstrip()
    rels_doc = format_combined_relationships_document(meta).rstrip()
    return (
        summary
        + "\n\n---\n\n## All nodes\n\n"
        + nodes_doc
        + "\n\n---\n\n## All relationships\n\n"
        + rels_doc
        + "\n"
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_markdown_tree(
    meta: GraphMetadata,
    root: Path,
    *,
    combine_markdown: bool = True,
    mermaid_body: str | None = None,
    include_viz_readme: bool = False,
    on_file: Callable[[Path], None] | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)

    if combine_markdown:
        nodes_doc = format_combined_nodes_document(meta)
        rels_doc = format_combined_relationships_document(meta)
        summary_path = root / "graph_summary.md"
        write_text(summary_path, format_graph_summary_with_embedded_documents(meta))
        if on_file:
            on_file(summary_path)

        nodes_combined = root / "nodes.md"
        write_text(nodes_combined, nodes_doc)
        if on_file:
            on_file(nodes_combined)

        rel_combined = root / "relationship.md"
        write_text(rel_combined, rels_doc)
        if on_file:
            on_file(rel_combined)

        readme_lines = [
            "# Graph export (graph-to-md)",
            "",
            "- [Graph summary](./graph_summary.md) — summary plus embedded nodes and relationships",
            "- [Nodes (combined)](./nodes.md)",
            "- [Relationships (combined)](./relationship.md)",
        ]
    else:
        nodes_dir = root / "nodes"
        rels_dir = root / "relationships"
        nodes_dir.mkdir(parents=True, exist_ok=True)
        rels_dir.mkdir(parents=True, exist_ok=True)

        summary_path = root / "graph_summary.md"
        write_text(summary_path, format_graph_summary(meta))
        if on_file:
            on_file(summary_path)

        sorted_nodes = sorted(meta.nodes, key=lambda n: n.id)
        sorted_rels = sorted(meta.relationships, key=lambda r: (r.type, r.id, r.start_node, r.end_node))

        for n in sorted_nodes:
            p = nodes_dir / f"node_{slugify_segment(n.id)}.md"
            write_text(p, format_node_markdown(n, meta))
            if on_file:
                on_file(p)

        for r in sorted_rels:
            p = rels_dir / f"rel_{slugify_segment(r.id)}.md"
            write_text(p, format_relationship_markdown(r, meta))
            if on_file:
                on_file(p)

        readme_lines = [
            "# Graph export (graph-to-md)",
            "",
            "- [Graph summary](./graph_summary.md)",
            "- [Nodes](./nodes/)",
            "- [Relationships](./relationships/)",
        ]

    if mermaid_body and mermaid_body.strip():
        readme_lines.extend(
            [
                "",
                "## Diagram (Mermaid)",
                "",
                "Source file: [graph/graph.mmd](./graph/graph.mmd)",
                "",
                "```mermaid",
                mermaid_body.strip(),
                "```",
            ]
        )
    if include_viz_readme:
        readme_lines.extend(["", "## Diagram (Graphviz)", "", "![Graph](./graph/graph.png)"])
    readme_lines.append("")
    readme_path = root / "README.md"
    write_text(readme_path, "\n".join(readme_lines))
    if on_file:
        on_file(readme_path)
