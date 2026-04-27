from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice


def write_sequence_mermaid(out: Path, entry_id: str, sl: FlowSlice) -> None:
    lines: list[str] = ["sequenceDiagram", f"  participant E as {entry_id[:200]}"]
    for u, v, ed in sl.edges:
        ul = _safe(u)
        vl = _safe(v)
        lab = ""
        if ed.get("labels"):
            lab = str(ed["labels"][-1])[:80]
        elif ed.get("condition"):
            lab = str(ed["condition"])[:80]
        arrow = f"  {ul}->>{vl}: {lab}" if lab else f"  {ul}->>{vl}: call"
        lines.append(arrow)
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s)[:48]
