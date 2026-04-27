from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import slice_from_entry
from md_generator.codeflow.detectors.entry_detector import apply_entry_detectors, resolve_entry_symbol_ids
from md_generator.codeflow.graph.builder import GraphBuildResult, build_graph, graph_to_serializable
from md_generator.codeflow.generators.html import write_html_bundle
from md_generator.codeflow.generators.markdown import write_flow_markdown
from md_generator.codeflow.generators.mermaid import write_flow_mermaid
from md_generator.codeflow.generators.sequence import write_sequence_mermaid
from md_generator.codeflow.ingestion.loader import LoadedWorkspace, collect_source_files
from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.parsers.base import ParserRegistry, register_defaults
from md_generator.codeflow.core.run_config import ScanConfig


def _parse_results_for_workspace(ws: LoadedWorkspace, cfg: ScanConfig) -> list[FileParseResult]:
    reg = ParserRegistry()
    register_defaults(reg)
    files = cfg.paths_override if cfg.paths_override else collect_source_files(ws.root, cfg.languages)
    results: list[FileParseResult] = []
    for p in files:
        lang = _lang_for_path(p)
        if cfg.languages == "python" and lang != "python":
            continue
        if cfg.languages == "java" and lang != "java":
            continue
        pr = reg.parse_file(p, ws.root, lang)
        if pr:
            results.append(pr)
    apply_entry_detectors(files, ws.root, results)
    return results


def _lang_for_path(p: Path) -> str:
    suf = p.suffix.lower()
    if suf == ".py":
        return "python"
    if suf == ".java":
        return "java"
    return "unknown"


def run_scan(cfg: ScanConfig, *, workspace: LoadedWorkspace | None = None) -> Path:
    """Analyze code under workspace root and write outputs."""
    ws = workspace or LoadedWorkspace(root=cfg.project_root.resolve(), cleanup_dir=None)

    parse_results = _parse_results_for_workspace(ws, cfg)
    gb: GraphBuildResult = build_graph(parse_results, ws.root)
    g = gb.graph

    out = cfg.output_path
    out.mkdir(parents=True, exist_ok=True)

    all_entries = [e for pr in parse_results for e in pr.entries]
    entry_ids = resolve_entry_symbol_ids(cfg.entry, all_entries)

    fmts = {x.strip().lower() for x in cfg.formats}

    entry_ids = [e for e in entry_ids if e in g]
    if not entry_ids:
        entry_ids = [n for n, d in g.nodes(data=True) if d.get("type") == "entry" and n in g]
    if not entry_ids:
        entry_ids = [n for n in g.nodes()][: min(10, max(1, g.number_of_nodes()))]

    include_map = cfg.parsed_include()

    for eid in entry_ids:
        if include_map:
            ndata = dict(g.nodes[eid]) if eid in g else {}
            ek = ndata.get("entry_kind")
            if ek and ek not in include_map:
                continue
        sl = slice_from_entry(g, eid, cfg.depth)
        slug = _slug(eid)
        sub = out / slug
        sub.mkdir(parents=True, exist_ok=True)
        if "md" in fmts:
            write_flow_markdown(sub / "flow.md", eid, sl, g)
        if "mermaid" in fmts:
            write_flow_mermaid(sub / "flow.mmd", eid, sl)
            write_sequence_mermaid(sub / "sequence.mmd", eid, sl)
        if "json" in fmts:
            sub_g = g.subgraph(sl.nodes).copy()
            sub_json = graph_to_serializable(sub_g)
            (sub / "graph.json").write_text(json.dumps(sub_json, indent=2), encoding="utf-8")
        if "html" in fmts:
            sub_g = g.subgraph(sl.nodes).copy()
            write_html_bundle(sub / "index.html", eid, sl, graph_to_serializable(sub_g))

    if "json" in fmts:
        full = graph_to_serializable(g)
        (out / "graph-full.json").write_text(json.dumps(full, indent=2), encoding="utf-8")

    return out


def _slug(entry_id: str) -> str:
    s = "".join(c if c.isalnum() or c in "._-" else "_" for c in entry_id)
    return s[:180] if len(s) > 180 else s


def build_output_zip(cfg: ScanConfig, workspace_root: Path | None = None) -> bytes:
    """Run scan into a temp dir and return zip bytes (for API)."""
    td = Path(tempfile.mkdtemp(prefix="codeflow-scan-"))
    try:
        root = workspace_root or cfg.project_root
        wc = LoadedWorkspace(root=root.resolve(), cleanup_dir=None)
        cfg2 = ScanConfig(
            project_root=root.resolve(),
            paths_override=cfg.paths_override,
            output_path=td / "out",
            formats=cfg.formats,
            depth=cfg.depth,
            languages=cfg.languages,
            entry=cfg.entry,
            include=cfg.include,
            exclude=cfg.exclude,
            include_internal=cfg.include_internal,
            async_mode=cfg.async_mode,
            jobs=cfg.jobs,
            runtime=cfg.runtime,
        )
        run_scan(cfg2, workspace=wc)
        buf = td / "bundle.zip"
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in (td / "out").rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(td).as_posix())
        return buf.read_bytes()
    finally:
        shutil.rmtree(td, ignore_errors=True)
