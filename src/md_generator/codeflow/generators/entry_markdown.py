"""Structured per-entry Markdown (Execution Flow Documentation)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.generators.flow_summary import format_flow_description, format_method_summary_lines
from md_generator.codeflow.models.ir import BusinessRule, EntryKind, EntryRecord


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def type_label_for_kind(kind: str | None) -> str:
    if not kind:
        return "Other"
    mapping = {
        EntryKind.API_REST.value: "API",
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


def write_system_overview(
    path: Path,
    rows: list[tuple[str, str, str, str, str]],
    *,
    project_hint: str | None = None,
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
    path.write_text("\n".join(lines), encoding="utf-8")
