from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice


def write_flow_markdown(out: Path, entry_id: str, sl: FlowSlice, full_graph: object) -> None:
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
    out.write_text("\n".join(lines), encoding="utf-8")
