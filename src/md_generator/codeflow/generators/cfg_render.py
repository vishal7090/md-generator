"""CFG → Mermaid / Markdown snippets (no graph imports beyond cfg_model)."""

from __future__ import annotations

import re

from md_generator.codeflow.graph.cfg_builder import cfg_to_serializable
from md_generator.codeflow.graph.cfg_model import CFG


def _mermaid_escape(s: str) -> str:
    return re.sub(r'["\n]', " ", s)[:80]


def build_mermaid_id_map(cfg: CFG) -> dict[str, str]:
    """Stable CFG node id → Mermaid node id (digits/special chars sanitized)."""
    id_map: dict[str, str] = {}
    for n in cfg.nodes.values():
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", n.id)
        if safe and safe[0].isdigit():
            safe = "n_" + safe
        if not safe:
            safe = "n_x"
        base = safe
        i = 0
        while safe in id_map.values():
            i += 1
            safe = f"{base}_{i}"
        id_map[n.id] = safe
    return id_map


def cfg_to_mermaid(cfg: CFG) -> str:
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
    return "\n".join(lines) + "\n"


def cfg_to_markdown_section(cfg: CFG, *, title: str = "## Control-flow graph (IR)") -> str:
    lines = [title, "", "```mermaid", cfg_to_mermaid(cfg).rstrip(), "```", ""]
    return "\n".join(lines)


def write_cfg_sidecar(out_dir, cfg: CFG) -> None:
    import json
    from pathlib import Path

    p = Path(out_dir)
    (p / "cfg.json").write_text(json.dumps(cfg_to_serializable(cfg), indent=2), encoding="utf-8")
    (p / "cfg.mmd").write_text(cfg_to_mermaid(cfg), encoding="utf-8")


def write_cfg_paths_sidecars(out_dir, cfg: CFG, paths: list[list[str]], *, truncated: bool = False) -> None:
    from pathlib import Path

    from md_generator.codeflow.generators.cfg_paths_markdown import paths_to_markdown
    from md_generator.codeflow.generators.cfg_paths_mermaid import paths_to_mermaid

    p = Path(out_dir)
    lookup = cfg.nodes
    (p / "cfg-paths.md").write_text(paths_to_markdown(cfg, paths, lookup, truncated=truncated), encoding="utf-8")
    (p / "cfg-paths.mmd").write_text(paths_to_mermaid(cfg, paths), encoding="utf-8")
