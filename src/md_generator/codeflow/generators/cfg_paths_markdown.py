"""CFG execution paths → Markdown (IR/CFG only)."""

from __future__ import annotations

from md_generator.codeflow.graph.cfg_model import CFG, CFGNode


def _exception_flow_section(cfg: CFG) -> list[str]:
    """Summarize try → catch edges and how success vs exception paths merge."""
    exc_edges = [e for e in cfg.edges if (e.label or "").startswith("exception:")]
    if not exc_edges:
        return []
    lines: list[str] = ["## Exception flow", ""]
    for e in exc_edges:
        tn = cfg.nodes.get(e.target)
        tgt = f"`{tn.kind}:{(tn.label or '').strip()}`" if tn else f"`{e.target}`"
        lines.append(f"- `{e.label}` → {tgt}")
    fin_ids = {nid for nid, n in cfg.nodes.items() if n.kind == "FINALLY"}
    if fin_ids:
        if any(e.label == "no_exception" and e.target in fin_ids for e in cfg.edges):
            lines.append("- Success (`no_exception`) → FINALLY, then `MERGE:try_exit`")
        lines.append("- Exception paths → CATCH → … → FINALLY → `MERGE:try_exit`")
    else:
        lines.append("- Success (`no_exception`) → `MERGE:try_exit`")
        lines.append("- Exception paths → CATCH → `MERGE:try_exit`")
    lines.append("")
    return lines


def _control_transfers_section(cfg: CFG) -> list[str]:
    kinds = {n.kind for n in cfg.nodes.values()}
    hit = kinds & {"BREAK", "CONTINUE", "RETURN"}
    if not hit:
        return []
    lines: list[str] = ["## Control transfers", ""]
    if "BREAK" in kinds:
        lines.append("- **break** → innermost `LOOP_EXIT`")
    if "CONTINUE" in kinds:
        lines.append("- **continue** → innermost `LOOP_HDR` (re-enter loop)")
    if "RETURN" in kinds:
        lines.append("- **return** → method `END`")
    lines.append("")
    return lines


def _path_probabilities_section(
    paths: list[list[str]],
    path_probabilities: list[float],
    node_lookup: dict[str, CFGNode],
    cfg: CFG,
) -> list[str]:
    lines: list[str] = ["## Path probabilities", ""]
    for i, (p, pr) in enumerate(zip(paths, path_probabilities), 1):
        labels: list[str] = []
        for nid in p:
            n = node_lookup.get(nid) or cfg.nodes.get(nid)
            if n is None:
                labels.append(f"?:{nid}")
            else:
                lbl = (n.label or "").strip()
                labels.append(f"{n.kind}:{lbl}" if lbl else n.kind)
        lines.append(f"{i}. " + " → ".join(labels) + f"  (`{pr:.4f}`)")
    lines.append("")
    return lines


def _runtime_observations_section(
    cfg: CFG,
    paths: list[list[str]],
    path_probabilities: list[float] | None,
) -> list[str]:
    if not any(e.runtime_prob is not None for e in cfg.edges):
        return []
    lines: list[str] = ["## Runtime observations", "", "_Edge weights normalized from trace counts (`runtime_prob`)._", ""]
    if path_probabilities and paths and len(path_probabilities) == len(paths):
        j = max(range(len(path_probabilities)), key=lambda i: path_probabilities[i])
        lines.append(f"- Highest-scoring enumerated path: **#{j + 1}** (≈ `{path_probabilities[j]:.4f}`)")
    lines.append("")
    return lines


def paths_to_markdown(
    cfg: CFG,
    paths: list[list[str]],
    node_lookup: dict[str, CFGNode],
    *,
    truncated: bool = False,
    path_probabilities: list[float] | None = None,
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
    if path_probabilities is not None and paths and len(path_probabilities) == len(paths):
        lines.extend(_path_probabilities_section(paths, path_probabilities, node_lookup, cfg))
    lines.extend(_control_transfers_section(cfg))
    lines.extend(_runtime_observations_section(cfg, paths, path_probabilities))
    lines.extend(_exception_flow_section(cfg))
    lines.append("")
    return "\n".join(lines)
