from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.graph.core.extractor import extract_to_markdown
from md_generator.graph.core.job_manager import GraphJobManager
from md_generator.graph.core.run_config import GraphRunConfig, VizConfig, load_graph_run_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export graph data to Markdown.")
    p.add_argument("--config", type=Path, default=None, help="Path to YAML config")
    p.add_argument("--source", default=None, choices=("networkx", "neo4j"))
    p.add_argument("--uri", default=None)
    p.add_argument("--user", default=None)
    p.add_argument("--password", default=None)
    p.add_argument(
        "--database",
        default=None,
        help="Neo4j database name (e.g. neo4j); passed to driver session(database=...)",
    )
    p.add_argument("--graph-file", type=Path, default=None)
    p.add_argument("--depth", type=int, default=None)
    p.add_argument("--start-node", default=None)
    p.add_argument("--max-nodes", type=int, default=None)
    p.add_argument("--max-edges", type=int, default=None)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--neo4j-id-mode", default=None, choices=("element_id", "internal_id"))
    p.add_argument(
        "--async",
        dest="async_job",
        action="store_true",
        help="Enqueue background job (prints job_id; uses SQLite job store)",
    )
    p.add_argument(
        "--markdown-layout",
        choices=("combined", "individual"),
        default=None,
        help="combined (default): nodes.md, relationship.md, graph_summary with embedded sections; "
        "individual: nodes/ and relationships/ per entity",
    )
    p.add_argument(
        "--individual",
        action="store_true",
        help="Shortcut for --markdown-layout individual",
    )
    p.add_argument(
        "--viz",
        action="store_true",
        help="Write output/graph/graph.dot and render PNG/SVG/PDF via Graphviz dot (if installed)",
    )
    p.add_argument(
        "--viz-formats",
        default=None,
        help="Comma-separated formats for --viz (default png,svg). Example: png,svg,pdf",
    )
    p.add_argument(
        "--no-mermaid",
        action="store_true",
        help="Disable Mermaid diagram (graph/graph.mmd and README fenced block)",
    )
    return p


def _apply_cli_overrides(cfg: GraphRunConfig, ns: argparse.Namespace) -> GraphRunConfig:
    from dataclasses import replace

    kw: dict = {}
    if ns.source:
        kw["source"] = ns.source
    if ns.uri is not None:
        kw["uri"] = ns.uri
    if ns.user is not None:
        kw["user"] = ns.user
    if ns.password is not None:
        kw["password"] = ns.password
    if ns.database is not None:
        kw["neo4j_database"] = ns.database or None
    if ns.graph_file is not None:
        kw["graph_file"] = ns.graph_file
    if ns.depth is not None:
        kw["depth"] = ns.depth
    if ns.start_node is not None:
        kw["start_node"] = ns.start_node or None
    if ns.max_nodes is not None:
        kw["max_nodes"] = ns.max_nodes
    if ns.max_edges is not None:
        kw["max_edges"] = ns.max_edges
    if ns.output is not None:
        kw["output_path"] = ns.output
    if ns.neo4j_id_mode is not None:
        kw["neo4j_id_mode"] = ns.neo4j_id_mode
    if ns.individual:
        kw["combine_markdown"] = False
    elif ns.markdown_layout == "individual":
        kw["combine_markdown"] = False
    elif ns.markdown_layout == "combined":
        kw["combine_markdown"] = True
    v = cfg.viz
    if ns.viz:
        if ns.viz_formats and ns.viz_formats.strip():
            fmts = tuple(x.strip().lower() for x in ns.viz_formats.split(",") if x.strip())
            if not fmts:
                fmts = ("png", "svg")
        else:
            fmts = v.formats
        v = VizConfig(enabled=True, mermaid=v.mermaid, formats=fmts)
    if ns.no_mermaid:
        v = replace(v, mermaid=False)
    if ns.viz or ns.no_mermaid:
        kw["viz"] = v
    return replace(cfg, **kw) if kw else cfg


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ns = build_parser().parse_args(argv)
    cfg = load_graph_run_config(ns.config, None)
    cfg = _apply_cli_overrides(cfg, ns)
    cfg = cfg.normalized()

    if cfg.source == "networkx" and cfg.graph_file is None:
        print("networkx source requires --graph-file or graph.graph_file in config", file=sys.stderr)
        return 2

    if ns.async_job:
        jobs = GraphJobManager()
        rec = jobs.create_job(cfg)
        jobs.run_job_thread(rec.job_id)
        print(rec.job_id)
        jobs.close()
        return 0

    extract_to_markdown(cfg)
    print(str(cfg.output_path.resolve()))
    return 0
