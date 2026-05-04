"""Shallow copy / clone helpers for CFG mutation (call expansion)."""

from __future__ import annotations

from md_generator.codeflow.graph.cfg_model import CFG, CFGEdge, CFGNode


def copy_cfg(cfg: CFG) -> CFG:
    out = CFG()
    out._next = cfg._next
    for nid, n in cfg.nodes.items():
        out.nodes[nid] = CFGNode(
            id=n.id,
            kind=n.kind,
            label=n.label,
            method_name=n.method_name,
            file_path=n.file_path,
            line=n.line,
        )
    out.edges = [CFGEdge(e.source, e.target, e.label) for e in cfg.edges]
    return out


def clone_cfg_with_prefix(src: CFG, prefix: str) -> tuple[CFG, dict[str, str]]:
    """Deep-clone nodes/edges with id prefix to avoid clashes when inlining."""
    out = CFG()
    mapping: dict[str, str] = {}
    for nid, n in src.nodes.items():
        new_id = f"{prefix}{nid}"
        mapping[nid] = new_id
        out.nodes[new_id] = CFGNode(
            id=new_id,
            kind=n.kind,
            label=n.label,
            method_name=n.method_name,
            file_path=n.file_path,
            line=n.line,
        )
    for e in src.edges:
        out.edges.append(CFGEdge(mapping[e.source], mapping[e.target], e.label))
    return out, mapping
