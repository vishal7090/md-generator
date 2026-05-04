"""CFG execution paths → Markdown (IR/CFG only)."""

from __future__ import annotations

from md_generator.codeflow.graph.cfg_model import CFG, CFGNode


def paths_to_markdown(
    cfg: CFG,
    paths: list[list[str]],
    node_lookup: dict[str, CFGNode],
    *,
    truncated: bool = False,
) -> str:
    """``node_lookup`` is typically ``cfg.nodes``; unknown ids render as ``?:id``."""
    lines = ["## Execution paths", ""]
    if not paths:
        lines.append("_No paths from START to END (missing nodes or disconnected graph)._")
        lines.append("")
    for i, p in enumerate(paths, 1):
        labels: list[str] = []
        for nid in p:
            n = node_lookup.get(nid) or cfg.nodes.get(nid)
            if n is None:
                labels.append(f"?:{nid}")
            else:
                lbl = (n.label or "").strip()
                labels.append(f"{n.kind}:{lbl}" if lbl else n.kind)
        lines.append(f"{i}. " + " → ".join(labels))
    if truncated:
        lines.append("")
        lines.append("_Enumeration stopped early (path or depth cap)._")
    lines.append("")
    return "\n".join(lines)
