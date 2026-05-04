from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph
from md_generator.codeflow.graph.enricher import (
    called_by_direct,
    called_by_transitive,
    impact_descendants,
    structural_dependency_bullets,
)


def write_flow_markdown(
    out: Path,
    entry_id: str,
    sl: FlowSlice,
    g: CodeflowGraph,
    *,
    list_cap: int = 80,
    intelligence_transitive_callers: bool = False,
    graph_include_structural: bool = False,
) -> None:
    lines: list[str] = []
    lines.append(f"# Entry: `{entry_id}`")
    lines.append("")
    lines.append("## Flow")
    lines.append("")
    if sl.truncated:
        lines.append("*Truncated by depth limit.*")
        lines.append("")
    if sl.cycle_nodes:
        lines.append(f"*Possible cycles or revisits near:* `{', '.join(sorted(sl.cycle_nodes))}`")
        lines.append("")
    for u, v, ed in sl.edges:
        cond = ed.get("condition") or ""
        labs = ed.get("labels") or []
        lab = labs[-1] if labs else cond
        et = ed.get("type", "sync")
        tail = f" ({lab})" if lab else ""
        async_note = " [async]" if ed.get("async_") or et == "async" else ""
        flags: list[str] = []
        if ed.get("recursive"):
            flags.append("recursive")
        if ed.get("unknown_call"):
            flags.append("unknown_call")
        flag_note = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"- `{u}` → `{v}`{tail}{async_note}{flag_note}")
    lines.append("")

    if intelligence_transitive_callers:
        cb = called_by_transitive(g, entry_id, list_cap)
        cb_blurb = (
            "Transitive upstream nodes (`nx.ancestors` on **dependency reachability**: "
            "CALLS + IMPORTS / INHERITS / … when present; excludes CONTAINS; capped)."
        )
    else:
        cb = called_by_direct(g, entry_id, list_cap)
        cb_blurb = (
            "Direct predecessors in **dependency reachability** "
            "(calls + structural relations when ``--graph-include-structural`` is on; capped)."
        )
    im = impact_descendants(g, entry_id, list_cap)
    lines.append("## Called By")
    lines.append("")
    lines.append(cb_blurb)
    lines.append("")
    if cb:
        for x in cb:
            lines.append(f"- `{x}`")
        if len(cb) >= list_cap:
            lines.append(f"- *…truncated at {list_cap} items.*")
    else:
        lines.append("*None in dependency reachability graph (entry missing or no inbound edges).*")
    lines.append("")
    lines.append("## Impact")
    lines.append("")
    lines.append(
        "Transitive downstream nodes (`nx.descendants` on **dependency reachability**; "
        "not the depth slice only; capped).",
    )
    lines.append("")
    if im:
        for x in im:
            lines.append(f"- `{x}`")
        if len(im) >= list_cap:
            lines.append(f"- *…truncated at {list_cap} items.*")
    else:
        lines.append("*None beyond this node (or empty downstream).*")
    lines.append("")

    if graph_include_structural:
        dep = structural_dependency_bullets(g, entry_id, list_cap)
        lines.append("## Dependencies")
        lines.append("")
        if dep:
            lines.extend(dep)
            if len(dep) >= list_cap:
                lines.append(f"- *…truncated at {list_cap} items.*")
        else:
            lines.append("*No structural edges for this entry's file/class.*")
        lines.append("")

    cond_lines: list[str] = []
    seen_c: set[tuple[str, str, str]] = set()
    for u, v, ed in sl.edges:
        cond = ed.get("condition") or ""
        labs = ed.get("labels") or []
        lab = (labs[-1] if labs else None) or cond
        if not lab:
            continue
        key = (u, v, str(lab))
        if key in seen_c:
            continue
        seen_c.add(key)
        cond_lines.append(f"- `{u}` → `{v}` — *{lab}*")
    if cond_lines:
        lines.append("## Conditions")
        lines.append("")
        lines.extend(cond_lines[: list_cap])
        lines.append("")

    if entry_id in g:
        d = g.nodes[entry_id]
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- **File:** `{d.get('file_path', '')}`")
        lines.append(f"- **Class:** `{d.get('class_name', '')}`")
        lines.append(f"- **Language:** `{d.get('language', '')}`")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
