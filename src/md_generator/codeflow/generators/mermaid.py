from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice


def _nid(idx: int) -> str:
    return f"n{idx}"


def write_flow_mermaid(out: Path, entry_id: str, sl: FlowSlice) -> None:
    lines: list[str] = ["flowchart TD"]
    idx = 0
    node_ids: dict[str, str] = {}

    def nid_for(label: str) -> str:
        nonlocal idx
        if label not in node_ids:
            node_ids[label] = _nid(idx)
            idx += 1
            esc = label.replace('"', "'")
            lines.append(f'  {node_ids[label]}["{esc}"]')
        return node_ids[label]

    for u, v, ed in sl.edges:
        a = nid_for(u)
        b = nid_for(v)
        labs = ed.get("labels") or []
        lab = labs[-1] if labs else ed.get("condition") or ""
        meta: list[str] = []
        if ed.get("recursive"):
            meta.append("recursive")
        if ed.get("unknown_call"):
            meta.append("unknown_call")
        if meta:
            lab = f"{lab}|{','.join(meta)}" if lab else ",".join(meta)
        if lab:
            esc = str(lab).replace('"', "'")[:120]
            lines.append(f"  {a} -->|{esc}| {b}")
        else:
            lines.append(f"  {a} --> {b}")

    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
