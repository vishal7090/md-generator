from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from md_generator.graph.core.models import GraphMetadata

logger = logging.getLogger(__name__)

_MERMAID_MAX_LABEL = 200


def _mermaid_sanitize_display(text: str, *, max_len: int = _MERMAID_MAX_LABEL) -> str:
    """Escape text for inside Mermaid `["..."]` and edge labels."""
    t = str(text).replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\\", "/")
    t = t.replace('"', "#quot;")
    t = t.replace("\n", "<br/>")
    t = t.replace("[", "(").replace("]", ")")
    t = t.replace("{", "(").replace("}", ")")
    t = t.replace("|", " ")
    t = t.strip() or " "
    if len(t) > max_len:
        t = t[: max_len - 3] + "..."
    return t


def metadata_to_mermaid_body(meta: GraphMetadata) -> str:
    """Return Mermaid source (no fences). Uses ``flowchart LR`` with stable synthetic node ids."""
    nodes_sorted = sorted(meta.nodes, key=lambda n: n.id)
    if not nodes_sorted and not meta.relationships:
        return "flowchart LR\n  empty[Empty graph]"
    id_map = {n.id: f"n{i}" for i, n in enumerate(nodes_sorted)}
    lines: list[str] = ["flowchart LR"]
    for n in nodes_sorted:
        mid = id_map[n.id]
        lab0 = ",".join(n.labels_sorted()) or "Node"
        lab = _mermaid_sanitize_display(f"{lab0} — {n.id}")
        lines.append(f'  {mid}["{lab}"]')
    for r in sorted(meta.relationships, key=lambda x: (x.type, x.id, x.start_node, x.end_node)):
        a = id_map.get(r.start_node)
        b = id_map.get(r.end_node)
        if not a or not b:
            continue
        typ = _mermaid_sanitize_display(r.type, max_len=80)
        lines.append(f'  {a} -->|"{typ}"| {b}')
    return "\n".join(lines)


def write_graph_mermaid(meta: GraphMetadata, root: Path) -> str:
    """Write ``graph/graph.mmd`` and return the diagram body (for README embedding)."""
    body = metadata_to_mermaid_body(meta)
    gdir = root / "graph"
    gdir.mkdir(parents=True, exist_ok=True)
    path = gdir / "graph.mmd"
    path.write_text(body + "\n", encoding="utf-8", newline="\n")
    return body


def _dot_escape(s: str) -> str:
    t = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{t}"'


def metadata_to_dot(meta: GraphMetadata) -> str:
    lines = ["digraph G {", "  rankdir=LR;"]
    for n in sorted(meta.nodes, key=lambda x: x.id):
        lab = ",".join(n.labels_sorted()) or "Node"
        lines.append(f"  {_dot_escape(n.id)} [label={_dot_escape(lab)}];")
    seen: set[tuple[str, str, str]] = set()
    for r in sorted(meta.relationships, key=lambda x: (x.type, x.id, x.start_node, x.end_node)):
        key = (r.start_node, r.end_node, r.id)
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"  {_dot_escape(r.start_node)} -> {_dot_escape(r.end_node)} "
            f"[label={_dot_escape(r.type)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def _which_dot() -> str | None:
    import os

    env = os.environ.get("GRAPHVIZ_DOT")
    if env and Path(env).is_file():
        return str(Path(env).resolve())
    return shutil.which("dot")


def write_graph_viz(meta: GraphMetadata, root: Path, *, formats: tuple[str, ...]) -> bool:
    """Write graph/graph.dot and optionally PNG/SVG via Graphviz. Returns True if PNG exists."""
    root.mkdir(parents=True, exist_ok=True)
    gdir = root / "graph"
    gdir.mkdir(parents=True, exist_ok=True)
    dot_path = gdir / "graph.dot"
    dot_path.write_text(metadata_to_dot(meta), encoding="utf-8", newline="\n")
    dot_exe = _which_dot()
    if not dot_exe:
        logger.info("Graphviz dot not found; skipped PNG/SVG (DOT written).")
        return False
    wrote_png = False
    for fmt in formats:
        fmt = fmt.lower().strip()
        if fmt not in ("png", "svg", "pdf"):
            continue
        out_path = gdir / f"graph.{fmt}"
        cmd = [dot_exe, f"-T{fmt}", "-o", str(out_path), str(dot_path)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            logger.warning("dot failed for %s: %s", fmt, (r.stderr or r.stdout or "").strip())
            continue
        if fmt == "png":
            wrote_png = True
    return wrote_png
