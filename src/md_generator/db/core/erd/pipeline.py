from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

from md_generator.db.core.erd.dot_emitter import build_dot
from md_generator.db.core.erd.filter import subgraph_full, subgraphs_per_schema, subgraphs_per_table
from md_generator.db.core.erd.mermaid_emitter import build_mermaid_er, mermaid_bundle_markdown
from md_generator.db.core.erd.mermaid_render import try_mermaid_py_png_svg
from md_generator.db.core.erd.render import render_dot_to, try_resolve_dot_executable
from md_generator.db.core.markdown_writer import slugify_segment
from md_generator.db.core.models import TableDetail
from md_generator.db.core.run_config import ErdConfig

logger = logging.getLogger(__name__)


class ErdExportResult(NamedTuple):
    artifacts: tuple[str, ...]
    engine: str | None  # graphviz | mermaid_py | mermaid_text


def count_erd_render_steps(details: list[TableDetail], erd: ErdConfig, *, dot_available: bool) -> int:
    if not details:
        return 0
    erd_n = erd.normalized()
    if erd_n.scope == "full":
        ngraphs = 1
    elif erd_n.scope == "per_schema":
        ngraphs = len(subgraphs_per_schema(details, erd_n.max_tables))
    else:
        ngraphs = len(subgraphs_per_table(details, erd_n.max_tables))
    steps_per = 3 if dot_available else 4
    return max(1, ngraphs * steps_per)


def _write_dot_render(
    root: Path,
    rel_base: str,
    graph_title: str,
    nodes: frozenset,
    edges: tuple,
    dot_exe: str,
    on_step: Callable[[str], None] | None,
) -> None:
    erd_dir = root / "erd"
    erd_dir.mkdir(parents=True, exist_ok=True)
    stem = erd_dir / rel_base
    stem.parent.mkdir(parents=True, exist_ok=True)
    dot_path = stem.with_suffix(".dot")
    dot_path.write_text(build_dot(graph_title, nodes, edges), encoding="utf-8", newline="\n")
    if on_step:
        on_step(f"erd:dot:{dot_path.relative_to(root).as_posix()}")
    png_path = stem.with_suffix(".png")
    svg_path = stem.with_suffix(".svg")
    render_dot_to(dot_exe, dot_path, png_path, "png")
    if on_step:
        on_step(f"erd:png:{png_path.relative_to(root).as_posix()}")
    render_dot_to(dot_exe, dot_path, svg_path, "svg")
    if on_step:
        on_step(f"erd:svg:{svg_path.relative_to(root).as_posix()}")


def _write_mermaid_bundle(
    root: Path,
    rel_base: str,
    graph_title: str,
    nodes: frozenset,
    edges: tuple,
    on_step: Callable[[str], None] | None,
) -> tuple[str, tuple[str, ...]]:
    """
    Write ``.mermaid`` + ``.md``; try ``mermaid-py`` for PNG/SVG.
    Returns (engine, relative_paths_for_readme_priority).
    """
    erd_dir = root / "erd"
    erd_dir.mkdir(parents=True, exist_ok=True)
    stem = erd_dir / rel_base
    stem.parent.mkdir(parents=True, exist_ok=True)
    diagram = build_mermaid_er(graph_title, nodes, edges)
    mermaid_path = stem.with_suffix(".mermaid")
    mermaid_path.write_text(diagram, encoding="utf-8", newline="\n")
    if on_step:
        on_step(f"erd:mermaid:{mermaid_path.relative_to(root).as_posix()}")
    md_path = stem.with_suffix(".md")
    md_path.write_text(mermaid_bundle_markdown(graph_title, diagram), encoding="utf-8", newline="\n")
    if on_step:
        on_step(f"erd:md:{md_path.relative_to(root).as_posix()}")
    if try_mermaid_py_png_svg(diagram, stem):
        if on_step:
            on_step(f"erd:png:{stem.with_suffix('.png').relative_to(root).as_posix()}")
        if on_step:
            on_step(f"erd:svg:{stem.with_suffix('.svg').relative_to(root).as_posix()}")
        rels = [
            stem.with_suffix(".png").relative_to(root).as_posix(),
            stem.with_suffix(".svg").relative_to(root).as_posix(),
            mermaid_path.relative_to(root).as_posix(),
            md_path.relative_to(root).as_posix(),
        ]
        return "mermaid_py", tuple(rels)
    rels = [
        md_path.relative_to(root).as_posix(),
        mermaid_path.relative_to(root).as_posix(),
    ]
    return "mermaid_text", tuple(rels)


def _export_one_graph(
    root: Path,
    rel_base: str,
    graph_title: str,
    nodes: frozenset,
    edges: tuple,
    *,
    dot_exe: str | None,
    on_step: Callable[[str], None] | None,
) -> tuple[str, tuple[str, ...]]:
    if not nodes:
        return "none", ()
    if dot_exe:
        _write_dot_render(root, rel_base, graph_title, nodes, edges, dot_exe, on_step)
        stem = root / "erd" / rel_base
        return (
            "graphviz",
            (
                stem.with_suffix(".png").relative_to(root).as_posix(),
                stem.with_suffix(".svg").relative_to(root).as_posix(),
            ),
        )
    eng, arts = _write_mermaid_bundle(root, rel_base, graph_title, nodes, edges, on_step)
    return eng, arts


def write_erd_outputs(
    root: Path,
    details: Sequence[TableDetail],
    erd: ErdConfig,
    *,
    on_step: Callable[[str], None] | None = None,
) -> ErdExportResult:
    """
    Prefer Graphviz (``dot``); if unavailable, fall back to Mermaid (``mermaid-py`` when installed
    for PNG/SVG via mermaid.ink, else ``.mermaid`` + fenced ``.md`` only).
    """
    root = root.resolve()
    dlist = list(details)
    if not dlist:
        return ErdExportResult((), None)

    erd_n = erd.normalized()
    dot_exe = try_resolve_dot_executable()
    if dot_exe:
        logger.info("ERD: using Graphviz (%s)", dot_exe)
    else:
        logger.info("ERD: Graphviz not found; using Mermaid fallback (install mermaid-py for PNG/SVG).")

    artifacts: list[str] = []
    engine: str | None = None
    scope = erd_n.scope

    if scope == "full":
        nodes, edges = subgraph_full(dlist, erd_n.max_tables)
        eng, arts = _export_one_graph(root, "full", "erd_full", nodes, edges, dot_exe=dot_exe, on_step=on_step)
        if eng == "none":
            return ErdExportResult((), None)
        engine = eng
        artifacts.extend(arts)
    elif scope == "per_schema":
        for sch, nodes, edges in subgraphs_per_schema(dlist, erd_n.max_tables):
            if not nodes:
                continue
            slug = slugify_segment(sch)
            base = f"by_schema/{slug}"
            eng, arts = _export_one_graph(
                root, base, f"erd_schema_{sch}", nodes, edges, dot_exe=dot_exe, on_step=on_step
            )
            if eng == "none":
                continue
            engine = eng
            artifacts.extend(arts)
    else:
        for slug_raw, nodes, edges in subgraphs_per_table(dlist, erd_n.max_tables):
            if not nodes:
                continue
            slug = slugify_segment(slug_raw)
            base = f"by_table/{slug}"
            eng, arts = _export_one_graph(
                root, base, f"erd_table_{slug_raw}", nodes, edges, dot_exe=dot_exe, on_step=on_step
            )
            if eng == "none":
                continue
            engine = eng
            artifacts.extend(arts)

    if not artifacts:
        return ErdExportResult((), None)
    return ErdExportResult(tuple(artifacts), engine)
