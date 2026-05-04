from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import slice_from_entry
from md_generator.codeflow.detectors.entry_detector import apply_entry_detectors, resolve_entry_symbol_ids
from md_generator.codeflow.detectors.entry_rank import sort_entry_ids
from md_generator.codeflow.graph.builder import GraphBuildResult, build_graph, graph_to_serializable
from md_generator.codeflow.graph.export_schema import to_stable_schema
from md_generator.codeflow.generators.flow_tree import flow_tree_to_serializable
from md_generator.codeflow.generators.html import write_html_bundle
from md_generator.codeflow.generators.business_rules_markdown import (
    write_business_rules_markdown,
    write_combined_entry_markdown,
)
from md_generator.codeflow.generators.entry_markdown import (
    pretty_start_method,
    type_label_for_kind,
    write_entry_markdown,
    write_system_overview,
)
from md_generator.codeflow.generators.flow_summary import one_line_summary
from md_generator.codeflow.generators.markdown import write_flow_markdown
from md_generator.codeflow.generators.mermaid import write_flow_mermaid
from md_generator.codeflow.generators.sequence import write_sequence_mermaid
from md_generator.codeflow.ingestion.loader import LoadedWorkspace, collect_source_files
from md_generator.codeflow.lang_dispatch import lang_for_path, normalize_language_filter, should_parse_file_lang
from md_generator.codeflow.models.ir import EntryRecord, FileParseResult
from md_generator.codeflow.parsers.base import ParserRegistry, register_defaults
from md_generator.codeflow.parsers.ir_enrich import enrich_parse_results_with_ir
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.models.ir_cfg import IRMethod


def _read_entries_file(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def _method_symbols_for_emit(g: nx.DiGraph, max_n: int, filter_re: str | None) -> list[str]:
    pat = re.compile(filter_re) if filter_re else None
    cand: list[str] = []
    for n, d in g.nodes(data=True):
        if not isinstance(n, str) or "::" not in n:
            continue
        if n.startswith("unknown::"):
            continue
        if d.get("type") not in ("method", "entry"):
            continue
        if pat and not pat.search(n):
            continue
        cand.append(n)
    cand = sorted(set(cand))
    return cand[:max_n]


def _root_symbol_ids(g: nx.DiGraph, max_n: int) -> list[str]:
    roots: list[str] = []
    for n in g.nodes():
        if not isinstance(n, str) or "::" not in n:
            continue
        if n.startswith("unknown::"):
            continue
        if g.in_degree(n) != 0:
            continue
        d = g.nodes[n]
        if d.get("type") not in ("method", "entry"):
            continue
        roots.append(n)
    return sorted(roots)[:max_n]


def _first_n_graph_symbol_ids(g: nx.DiGraph, max_n: int) -> list[str]:
    ids = sorted(
        n for n in g.nodes() if isinstance(n, str) and "::" in n and not n.startswith("unknown::")
    )
    return ids[:max_n]


def _resolve_scan_entry_ids(cfg: ScanConfig, g: nx.DiGraph, all_entries: list[EntryRecord]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []

    if cfg.entry:
        ids = [e for e in cfg.entry if e in g]
        missing = [e for e in cfg.entry if e not in g]
        if missing:
            warnings.append(
                f"{len(missing)} explicit entry symbol(s) not found in graph (showing up to 5): {missing[:5]}",
            )
        if ids:
            return ids, warnings
        warnings.append("No explicit entry symbols resolved in graph; trying other strategies.")

    if cfg.entries_file:
        raw = _read_entries_file(cfg.entries_file.resolve())
        ids = [x for x in raw if x in g]
        missing = [x for x in raw if x not in g]
        if missing:
            warnings.append(
                f"{len(missing)} entries_file symbol(s) not in graph (showing up to 5): {missing[:5]}",
            )
        if ids:
            return ids, warnings
        warnings.append("entries_file produced no symbols present in graph; trying other strategies.")

    if cfg.emit_entry_per_method:
        cap = cfg.emit_entry_max if cfg.emit_entry_max is not None else 10_000
        ids = _method_symbols_for_emit(g, cap, cfg.emit_entry_filter)
        if len(ids) >= cap:
            warnings.append(f"emit_entry_per_method capped at {cap} symbols (emit_entry_max).")
        if not ids:
            warnings.append("emit_entry_per_method produced no method symbols in graph.")
        return ids, warnings

    entry_ids = resolve_entry_symbol_ids(None, all_entries)
    entry_ids = [e for e in entry_ids if e in g]
    if entry_ids:
        return entry_ids, warnings

    entry_ids = [n for n, d in g.nodes(data=True) if d.get("type") == "entry" and n in g]
    if entry_ids:
        return entry_ids, warnings

    if cfg.entry_fallback == "none":
        warnings.append(
            "No entry symbols after detection (entry_fallback=none). No per-entry output directories.",
        )
        return [], warnings

    if cfg.entry_fallback == "roots":
        entry_ids = _root_symbol_ids(g, cfg.entry_fallback_max)
        if entry_ids:
            warnings.append(
                "No detected entries; used entry_fallback=roots (in-degree 0 symbols). Prefer --entry or --entries-file.",
            )
        else:
            warnings.append(
                "entry_fallback=roots found no suitable roots; set --entry, --entries-file, or entry_fallback=first_n.",
            )
        return entry_ids, warnings

    entry_ids = _first_n_graph_symbol_ids(g, cfg.entry_fallback_max)
    if entry_ids:
        warnings.append(
            "No detected entries; used entry_fallback=first_n (lexicographic). Prefer --entry or --entries-file.",
        )
    return entry_ids, warnings


def _write_scan_summary(
    path: Path,
    *,
    project_root: Path,
    parse_count: int,
    g: nx.DiGraph,
    entry_ids: list[str],
    emitted_slugs: int,
    warnings: list[str],
    cfg: ScanConfig,
) -> None:
    lines = [
        "# Scan summary",
        "",
        f"- **Project root:** `{project_root.resolve().as_posix()}`",
        f"- **Files parsed:** {parse_count}",
        f"- **Graph nodes:** {g.number_of_nodes()}",
        f"- **Graph edges:** {g.number_of_edges()}",
        f"- **Resolved entry ids:** {len(entry_ids)}",
        f"- **Output slugs emitted:** {emitted_slugs}",
        f"- **entry_fallback:** `{cfg.entry_fallback}`",
        f"- **emit_entry_per_method:** {cfg.emit_entry_per_method}",
    ]
    if cfg.emit_entry_per_method:
        lines.append(
            "- **Per-entry output:** nested under `methods/<slug>/` when using per-method mode",
        )
    lines += [
        f"- **emit_graph_schema:** {cfg.emit_graph_schema}",
        f"- **intelligence_list_cap:** {cfg.intelligence_list_cap}",
        f"- **emit_cfg:** {cfg.emit_cfg}",
        f"- **cfg_max_nodes:** {cfg.cfg_max_nodes}",
        f"- **cfg_inline_calls:** {cfg.cfg_inline_calls}",
        f"- **cfg_call_depth:** {cfg.cfg_call_depth}",
        f"- **cfg_max_paths:** {cfg.cfg_max_paths}",
        f"- **cfg_path_max_depth:** {cfg.cfg_path_max_depth}",
        f"- **cfg_loop_visits:** {cfg.cfg_loop_visits}",
        f"- **graph_include_structural:** {cfg.graph_include_structural}",
        f"- **intelligence_transitive_callers:** {cfg.intelligence_transitive_callers}",
        f"- **emit_system_graph_stats:** {cfg.emit_system_graph_stats}",
        f"- **emit_llm_entry_sidecar:** {cfg.emit_llm_entry_sidecar}",
        "",
    ]
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")
    lines.append(
        "Static graph only: unresolved dynamic calls appear as `unknown::*` nodes. "
        "Large repos should use `--emit-entry-max` / `entry_fallback_max` to limit output.",
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _parse_results_for_workspace(ws: LoadedWorkspace, cfg: ScanConfig) -> list[FileParseResult]:
    reg = ParserRegistry()
    register_defaults(reg)
    files = cfg.paths_override if cfg.paths_override else collect_source_files(ws.root, cfg.languages)
    allowed = normalize_language_filter(cfg.languages)
    results: list[FileParseResult] = []
    for p in files:
        lang = lang_for_path(p)
        if not should_parse_file_lang(lang, allowed):
            continue
        pr = reg.parse_file(p, ws.root, lang)
        if pr:
            results.append(pr)
    apply_entry_detectors(files, ws.root, results, cfg)
    return results


def run_scan(cfg: ScanConfig, *, workspace: LoadedWorkspace | None = None) -> Path:
    """Analyze code under workspace root and write outputs."""
    if cfg.verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
        logging.getLogger("md_generator.codeflow").setLevel(logging.DEBUG)

    ws = workspace or LoadedWorkspace(root=cfg.project_root.resolve(), cleanup_dir=None)

    parse_results = _parse_results_for_workspace(ws, cfg)
    enrich_parse_results_with_ir(parse_results, cfg, ws.root)
    gb: GraphBuildResult = build_graph(
        parse_results,
        ws.root,
        include_structural=cfg.graph_include_structural,
    )
    g = gb.graph

    out = cfg.output_path
    out.mkdir(parents=True, exist_ok=True)

    all_entries = [e for pr in parse_results for e in pr.entries]
    entry_ids, scan_warnings = _resolve_scan_entry_ids(cfg, g, all_entries)

    fmts = {x.strip().lower() for x in cfg.formats}

    entry_ids = sort_entry_ids(entry_ids, g, all_entries)
    entry_by_symbol = {e.symbol_id: e for e in all_entries}

    include_map = cfg.parsed_include()
    overview_rows: list[tuple[str, str, str, str, str]] = []
    emitted_slugs = 0
    entry_base = out / "methods" if cfg.emit_entry_per_method else out
    if cfg.emit_entry_per_method:
        entry_base.mkdir(parents=True, exist_ok=True)
    link_prefix = "methods/" if cfg.emit_entry_per_method else ""

    method_cfgs_for_cfg = None
    if cfg.emit_cfg:
        from md_generator.codeflow.graph.call_expander import build_method_cfg_index

        method_cfgs_for_cfg = build_method_cfg_index(parse_results, cfg.cfg_max_nodes)

    for eid in entry_ids:
        if include_map:
            ndata = dict(g.nodes[eid]) if eid in g else {}
            ek = ndata.get("entry_kind")
            if ek and ek not in include_map:
                continue
        emitted_slugs += 1
        sl = slice_from_entry(g, eid, cfg.depth)
        slug = _slug(eid)
        sub = entry_base / slug
        sub.mkdir(parents=True, exist_ok=True)
        rec = entry_by_symbol.get(eid)
        if "md" in fmts:
            write_flow_markdown(
                sub / "flow.md",
                eid,
                sl,
                g,
                list_cap=cfg.intelligence_list_cap,
                intelligence_transitive_callers=cfg.intelligence_transitive_callers,
                graph_include_structural=cfg.graph_include_structural,
            )
            rules = None
            if cfg.business_rules:
                from md_generator.codeflow.rules.collector import collect_business_rules

                rules = collect_business_rules(
                    eid,
                    sl,
                    g,
                    parse_results,
                    cfg,
                    project_root=ws.root.resolve(),
                )
                write_business_rules_markdown(
                    sub / "business_rules.md",
                    rules,
                    entry_hint=eid,
                )
                write_entry_markdown(
                    sub / "entry.md",
                    eid,
                    sl,
                    g,
                    rec,
                    rules=rules,
                    intelligence_cap=cfg.intelligence_list_cap,
                    graph_include_structural=cfg.graph_include_structural,
                    intelligence_transitive_callers=cfg.intelligence_transitive_callers,
                )
                if cfg.business_rules_combined:
                    write_combined_entry_markdown(
                        sub / "entry.md",
                        sub / "business_rules.md",
                        sub / "entry.combined.md",
                    )
            else:
                write_entry_markdown(
                    sub / "entry.md",
                    eid,
                    sl,
                    g,
                    rec,
                    rules=None,
                    intelligence_cap=cfg.intelligence_list_cap,
                    graph_include_structural=cfg.graph_include_structural,
                    intelligence_transitive_callers=cfg.intelligence_transitive_callers,
                )
            if eid in g:
                k = rec.kind.value if rec else g.nodes[eid].get("entry_kind")
            else:
                k = rec.kind.value if rec else None
            overview_rows.append(
                (
                    slug,
                    type_label_for_kind(k),
                    pretty_start_method(g, eid),
                    f"[entry](./{link_prefix}{slug}/entry.md)",
                    one_line_summary(sl, g),
                ),
            )
            if cfg.emit_llm_entry_sidecar:
                from md_generator.codeflow.generators.entry_markdown import write_llm_entry_sidecar

                write_llm_entry_sidecar(sub, eid, emit_cfg=cfg.emit_cfg)
        if cfg.emit_flow_tree_json:
            (sub / "flow-tree.json").write_text(
                json.dumps(flow_tree_to_serializable(eid, sl, g), indent=2),
                encoding="utf-8",
            )
        if cfg.emit_cfg:
            ir_m = _lookup_ir_method(eid, parse_results)
            if ir_m is not None:
                from md_generator.codeflow.graph.call_expander import expand_cfg_calls
                from md_generator.codeflow.graph.cfg_builder import build_cfg_from_ir
                from md_generator.codeflow.graph.path_enumerator import PathResult, enumerate_paths, find_cfg_end_id, find_cfg_start_id
                from md_generator.codeflow.generators.cfg_paths_markdown import paths_to_markdown
                from md_generator.codeflow.generators.cfg_render import cfg_to_markdown_section, write_cfg_paths_sidecars, write_cfg_sidecar

                c = build_cfg_from_ir(ir_m, max_nodes=cfg.cfg_max_nodes)
                c = expand_cfg_calls(
                    c,
                    method_cfgs_for_cfg or {},
                    max_call_depth=cfg.cfg_call_depth,
                    inline_calls=cfg.cfg_inline_calls,
                )
                write_cfg_sidecar(sub, c)
                sid = find_cfg_start_id(c)
                eid_end = find_cfg_end_id(c)
                path_res = (
                    enumerate_paths(
                        c,
                        sid,
                        eid_end,
                        max_paths=cfg.cfg_max_paths,
                        max_depth=cfg.cfg_path_max_depth,
                        max_loop_visits=cfg.cfg_loop_visits,
                    )
                    if sid and eid_end
                    else PathResult()
                )
                write_cfg_paths_sidecars(sub, c, path_res.paths, truncated=path_res.truncated)
                if "md" in fmts:
                    flow_path = sub / "flow.md"
                    extra = cfg_to_markdown_section(c) + "\n" + paths_to_markdown(
                        c, path_res.paths, c.nodes, truncated=path_res.truncated
                    )
                    flow_path.write_text(flow_path.read_text(encoding="utf-8") + "\n" + extra, encoding="utf-8")
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
        if cfg.emit_graph_schema:
            sch = to_stable_schema(g)
            (out / "graph-schema.json").write_text(json.dumps(sch, indent=2), encoding="utf-8")

    if "md" in fmts and overview_rows:
        write_system_overview(
            out / "system_overview.md",
            overview_rows,
            project_hint=f"Project: `{ws.root.resolve().as_posix()}`",
            graph=g if cfg.emit_system_graph_stats else None,
            emit_graph_stats=cfg.emit_system_graph_stats,
        )

    if cfg.write_scan_summary:
        _write_scan_summary(
            out / "scan-summary.md",
            project_root=ws.root,
            parse_count=len(parse_results),
            g=g,
            entry_ids=entry_ids,
            emitted_slugs=emitted_slugs,
            warnings=scan_warnings,
            cfg=cfg,
        )

    return out


def _lookup_ir_method(entry_id: str, parse_results: list[FileParseResult]) -> IRMethod | None:
    for pr in parse_results:
        for ir in pr.ir_methods:
            if isinstance(ir, IRMethod) and ir.symbol_id == entry_id:
                return ir
    return None


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
            business_rules=cfg.business_rules,
            business_rules_sql=cfg.business_rules_sql,
            business_rules_combined=cfg.business_rules_combined,
            entry_fallback=cfg.entry_fallback,
            entry_fallback_max=cfg.entry_fallback_max,
            emit_entry_per_method=cfg.emit_entry_per_method,
            emit_entry_max=cfg.emit_entry_max,
            emit_entry_filter=cfg.emit_entry_filter,
            entries_file=cfg.entries_file,
            write_scan_summary=cfg.write_scan_summary,
            liferay_portlet_base_classes=cfg.liferay_portlet_base_classes,
            codeflow_config_path=cfg.codeflow_config_path,
            emit_flow_tree_json=cfg.emit_flow_tree_json,
            verbose=cfg.verbose,
            emit_graph_schema=cfg.emit_graph_schema,
            intelligence_list_cap=cfg.intelligence_list_cap,
            emit_cfg=cfg.emit_cfg,
            cfg_max_nodes=cfg.cfg_max_nodes,
            cfg_inline_calls=cfg.cfg_inline_calls,
            cfg_call_depth=cfg.cfg_call_depth,
            cfg_max_paths=cfg.cfg_max_paths,
            cfg_path_max_depth=cfg.cfg_path_max_depth,
            cfg_loop_visits=cfg.cfg_loop_visits,
            graph_include_structural=cfg.graph_include_structural,
            intelligence_transitive_callers=cfg.intelligence_transitive_callers,
            emit_system_graph_stats=cfg.emit_system_graph_stats,
            emit_llm_entry_sidecar=cfg.emit_llm_entry_sidecar,
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
