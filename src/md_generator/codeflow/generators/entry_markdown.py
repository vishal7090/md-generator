"""Structured per-entry Markdown (Execution Flow Documentation)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.generators.flow_summary import format_flow_description, format_method_summary_lines
from md_generator.codeflow.graph import relations as graph_rel
from md_generator.codeflow.graph.enricher import (
    called_by_direct,
    called_by_transitive,
    impact_descendants,
    structural_dependency_bullets,
)
from md_generator.codeflow.models.ir import BusinessRule, EntryKind, EntryRecord


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def type_label_for_kind(kind: str | None) -> str:
    if not kind:
        return "Other"
    mapping = {
        EntryKind.API_REST.value: "API",
        EntryKind.PORTLET.value: "Portlet",
        EntryKind.KAFKA.value: "Event",
        EntryKind.QUEUE.value: "Event",
        EntryKind.SCHEDULER.value: "Scheduler",
        EntryKind.MAIN.value: "Main",
        EntryKind.CLI.value: "CLI",
        EntryKind.UNKNOWN.value: "Other",
    }
    return mapping.get(kind, "Other")


def _subtitle(entry_id: str, entry_record: EntryRecord | None, g: nx.DiGraph) -> str | None:
    if entry_record and entry_record.label.strip():
        lab = entry_record.label.strip()
        up = lab.upper()
        if any(m in up for m in ("GET ", "POST ", "PUT ", "DELETE ", "PATCH ")) or "`/" in lab or "/" in lab:
            return lab
    if entry_id in g:
        el = g.nodes[entry_id].get("entry_label")
        if el and str(el).strip():
            s = str(el).strip()
            if "/" in s or any(m in s.upper() for m in ("GET ", "POST ", "PUT ")):
                return s
    tail = entry_id.split("::", 1)[-1] if "::" in entry_id else entry_id
    return tail.replace("_", " ") if tail else None


def pretty_start_method(g: nx.DiGraph, entry_id: str) -> str:
    if entry_id not in g:
        tail = entry_id.split("::")[-1] if "::" in entry_id else entry_id
        if "." in tail:
            c, m = tail.rsplit(".", 1)
            return f"{c}.{m}()"
        return f"{tail}()"
    d = g.nodes[entry_id]
    cn = d.get("class_name")
    mn = d.get("method_name")
    if mn and cn:
        return f"{cn}.{mn}()"
    if mn:
        return f"{mn}()"
    tail = entry_id.split("::")[-1]
    return tail if tail.endswith(")") else f"{tail}()"


def _async_event_lines(sl: FlowSlice, g: nx.DiGraph) -> list[str]:
    lines: list[str] = []
    for _u, v, ed in sl.edges:
        if ed.get("async_") or ed.get("type") == "async":
            lines.append(f"- Async call to `{v}`")
        if v in g:
            ek = g.nodes[v].get("entry_kind")
            if ek in (EntryKind.KAFKA.value, EntryKind.QUEUE.value):
                lab = g.nodes[v].get("entry_label") or v
                lines.append(f"- Event-style target (`{ek}`): {lab}")
    return lines


def _collect_entry_tags(entry_id: str, g: nx.DiGraph) -> list[str]:
    if entry_id not in g:
        return []
    d = g.nodes[entry_id]
    tags = {str(x) for x in (d.get("tags") or []) if x}
    for ek in ("entry_kind", "type"):
        v = d.get(ek)
        if v:
            tags.add(str(v))
    for _, _succ, ed in g.out_edges(entry_id, data=True):
        if ed.get("async_") or ed.get("type") == "async":
            tags.add("async_outbound")
            break
    return sorted(tags)


def _graph_inventory_lines(graph: nx.DiGraph, top_n: int = 10) -> list[str]:
    from md_generator.codeflow.graph.enricher import call_graph_view

    rel_counts: dict[str, int] = {}
    for _, _, ed in graph.edges(data=True):
        k = str(ed.get("relation") or graph_rel.REL_CALLS)
        rel_counts[k] = rel_counts.get(k, 0) + 1
    lines = [
        "## Graph inventory",
        "",
        f"- **Nodes:** {graph.number_of_nodes()}",
        f"- **Edges:** {graph.number_of_edges()}",
        "",
        "**Edges by relation**",
        "",
    ]
    for k in sorted(rel_counts.keys()):
        lines.append(f"- `{k}`: {rel_counts[k]}")
    lines += ["", f"**Top call-graph out-degree (first {top_n})**", ""]
    cg = call_graph_view(graph)
    ranked = sorted(((n, cg.out_degree(n)) for n in cg.nodes()), key=lambda t: -t[1])[:top_n]
    for n, deg in ranked:
        lines.append(f"- `{n}` → {deg}")
    lines.append("")
    return lines


def _decision_bullets(sl: FlowSlice) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for u, v, ed in sl.edges:
        cond = ed.get("condition") or ""
        labs = ed.get("labels") or []
        lab = (labs[-1] if labs else None) or cond
        if not lab:
            continue
        key = (u, v, str(lab))
        if key in seen:
            continue
        seen.add(key)
        out.append(f"- `{u}` → `{v}` — *{lab}*")
    return out


def write_entry_markdown(
    path: Path,
    entry_id: str,
    sl: FlowSlice,
    g: nx.DiGraph,
    entry_record: EntryRecord | None,
    rules: Sequence[BusinessRule] | None = None,
    *,
    intelligence_cap: int = 80,
    graph_include_structural: bool = False,
    intelligence_transitive_callers: bool = False,
) -> None:
    lines: list[str] = []
    lines.append("# Execution Flow Documentation")
    lines.append("")
    sub = _subtitle(entry_id, entry_record, g)
    if sub:
        lines.append(f"*{sub}*")
        lines.append("")
    lines.append("## Entry Point")
    lines.append("")
    lines.append(f"- {pretty_start_method(g, entry_id)}")
    lines.append("")
    if entry_record is not None:
        kind = entry_record.kind.value
    elif entry_id in g:
        kind = g.nodes[entry_id].get("entry_kind")
    else:
        kind = None
    lines.append("## Type")
    lines.append("")
    lines.append(type_label_for_kind(kind))
    lines.append("")
    lines.append("## Flow Description")
    lines.append("")
    lines.extend(format_flow_description(sl, g))
    lines.append("")
    lines.append("## Method Summary")
    lines.append("")
    lines.extend(format_method_summary_lines(sl, g, entry_id))
    lines.append("")

    if intelligence_transitive_callers:
        cb = called_by_transitive(g, entry_id, intelligence_cap)
        cb_blurb = "*Transitive callers (ancestors in call graph; static analysis; capped).*"
    else:
        cb = called_by_direct(g, entry_id, intelligence_cap)
        cb_blurb = "*Direct callers (full call graph; static analysis; capped).*"
    im = impact_descendants(g, entry_id, intelligence_cap)
    lines.append("## Called By")
    lines.append("")
    lines.append(cb_blurb)
    lines.append("")
    if cb:
        for x in cb:
            lines.append(f"- `{x}`")
        if len(cb) >= intelligence_cap:
            lines.append(f"- *…truncated at {intelligence_cap} items.*")
    else:
        lines.append("*None in call graph or entry not found.*")
    lines.append("")
    lines.append("## Impact")
    lines.append("")
    lines.append("*Transitive callees from this entry (call graph; capped).*")
    lines.append("")
    if im:
        for x in im:
            lines.append(f"- `{x}`")
        if len(im) >= intelligence_cap:
            lines.append(f"- *…truncated at {intelligence_cap} items.*")
    else:
        lines.append("*None or empty downstream.*")
    lines.append("")

    lines.append("## Dependencies")
    lines.append("")
    if graph_include_structural:
        dep = structural_dependency_bullets(g, entry_id, intelligence_cap)
        if dep:
            lines.extend(dep)
            if len(dep) >= intelligence_cap:
                lines.append(f"- *…truncated at {intelligence_cap} items.*")
        else:
            lines.append(
                "*No structural edges for this symbol's file/class, or class context missing. "
                "Use Java sources with `--graph-include-structural`.*",
            )
    else:
        lines.append(
            "Enable **`--graph-include-structural`** (Java) to list imports and inheritance here. "
            "Structural view is also summarized in `graph-schema.json` when `--emit-graph-schema` is used with `json`.",
        )
    lines.append("")

    if entry_id in g:
        d = g.nodes[entry_id]
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- **File:** `{_md_escape(str(d.get('file_path', '')))}`")
        lines.append(f"- **Class:** `{_md_escape(str(d.get('class_name', '')))}`")
        lines.append(f"- **Language:** `{_md_escape(str(d.get('language', '')))}`")
        tag_list = _collect_entry_tags(entry_id, g)
        if tag_list:
            lines.append(f"- **Tags:** {', '.join(_md_escape(t) for t in tag_list)}")
        lines.append("")

    async_lines = _async_event_lines(sl, g)
    lines.append("## Async / Event Flow")
    lines.append("")
    if async_lines:
        lines.extend(async_lines)
    else:
        lines.append("*None detected in this slice.*")
    lines.append("")

    dec = _decision_bullets(sl)
    if dec:
        lines.append("## Decision Points")
        lines.append("")
        lines.extend(dec)
        lines.append("")

    if rules is not None:
        lines.append("## Business rules")
        lines.append("")
        if rules:
            for r in list(rules)[:4]:
                d = " ".join(r.detail.splitlines())[:140]
                lines.append(f"- **{_md_escape(r.title)}** (`{r.source}`, line {r.line}) — {_md_escape(d)}")
            if len(rules) > 4:
                lines.append(f"- *…and {len(rules) - 4} more in the full rules file.*")
        else:
            lines.append("*No detailed rules extracted for this slice.*")
        lines.append("")
        lines.append("[Full business rules](./business_rules.md)")
        lines.append("")

    lines.append("## Call graph (detail)")
    lines.append("")
    lines.append("See `flow.md` in this directory for the flat edge list.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_llm_entry_sidecar(sub: Path, entry_id: str, *, emit_cfg: bool = False) -> None:
    """Short pointer doc for LLM consumption (avoids duplicating full entry.md)."""
    lines = [
        "# LLM-oriented entry summary",
        "",
        f"- **Entry symbol:** `{entry_id}`",
        "- **Full narrative:** [entry.md](./entry.md)",
        "- **Flat call / condition list:** [flow.md](./flow.md)",
    ]
    if emit_cfg:
        lines.append("- **CFG paths (when emitted):** [cfg-paths.md](./cfg-paths.md)")
    lines.append("")
    (sub / "entry.llm.md").write_text("\n".join(lines), encoding="utf-8")


def write_system_overview(
    path: Path,
    rows: list[tuple[str, str, str, str, str]],
    *,
    project_hint: str | None = None,
    graph: nx.DiGraph | None = None,
    emit_graph_stats: bool = False,
) -> None:
    """Write root overview. Each row: ``(slug, type_label, start_method, link_line, one_line)``.

    ``link_line`` is typically ``[entry](./slug/entry.md)``.
    """
    lines: list[str] = []
    lines.append("# System overview")
    lines.append("")
    if project_hint:
        lines.append(project_hint)
        lines.append("")
    lines.append("Entries are listed in **priority order** (API, event, scheduler, main, …).")
    lines.append("")
    lines.append("| Type | Start method | Doc | Summary |")
    lines.append("| --- | --- | --- | --- |")
    for slug, typ, start_m, link, summary in rows:
        safe = summary.replace("|", "\\|")
        lines.append(f"| {typ} | `{start_m}` | {link} | {safe} |")
    lines.append("")
    if emit_graph_stats and graph is not None:
        lines.extend(_graph_inventory_lines(graph))
    path.write_text("\n".join(lines), encoding="utf-8")
