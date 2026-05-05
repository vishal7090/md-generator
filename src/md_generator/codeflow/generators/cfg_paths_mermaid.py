"""CFG + highlighted first path → Mermaid (comments only for highlight; valid flowchart)."""

from __future__ import annotations

from md_generator.codeflow.generators.cfg_render import _mermaid_escape, build_mermaid_id_map
from md_generator.codeflow.graph.cfg_model import CFG


def paths_to_mermaid(cfg: CFG, paths: list[list[str]]) -> str:
    lines = ["flowchart TD"]
    id_map = build_mermaid_id_map(cfg)
    for n in cfg.nodes.values():
        sid = id_map[n.id]
        shape = "[" + _mermaid_escape(f"{n.kind}: {n.label}") + "]"
        lines.append(f"  {sid}{shape}")
    for e in cfg.edges:
        a = id_map.get(e.source, "missing_src")
        b = id_map.get(e.target, "missing_dst")
        lab = _mermaid_escape(e.label or "") if e.label else ""
        if lab:
            lines.append(f"  {a} -->|{lab}| {b}")
        else:
            lines.append(f"  {a} --> {b}")
    if paths and paths[0]:
        p0 = paths[0]
        for i in range(len(p0) - 1):
            a = id_map.get(p0[i], p0[i])
            b = id_map.get(p0[i + 1], p0[i + 1])
            lines.append(f"  %% path0: {a} -> {b}")
    return "\n".join(lines) + "\n"
