from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from md_generator.codeflow.analyzers.flow_analyzer import slice_from_entry
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, unique_predecessor_count
from md_generator.codeflow.detectors.entry_detector import apply_entry_detectors, resolve_entry_symbol_ids
from md_generator.codeflow.detectors.entry_rank import sort_entry_ids
from md_generator.codeflow.graph.builder import GraphBuildResult, build_graph, graph_to_serializable
from md_generator.codeflow.graph.clustering import communities_for_mode, file_cluster_labels
from md_generator.codeflow.graph.diff_analysis import PR_IMPACT_LIST_CAP, DiffAnalysisError, diff_impact_nodes, git_changed_files, nodes_touching_files
from md_generator.codeflow.graph.event_graph import apply_event_edges
from md_generator.codeflow.graph.multi_repo import link_cross_repo_imports, merge_graphs, prefix_parse_results, repo_label
from md_generator.codeflow.graph.query_engine import execute_query
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
from md_generator.codeflow.parsers.unified_parser import parse_source_file
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


def _method_symbols_for_emit(g: CodeflowGraph, max_n: int, filter_re: str | None) -> list[str]:
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


def _root_symbol_ids(g: CodeflowGraph, max_n: int) -> list[str]:
    roots: list[str] = []
    for n in g.nodes():
        if not isinstance(n, str) or "::" not in n:
            continue
        if n.startswith("unknown::"):
            continue
        if unique_predecessor_count(g, n) != 0:
            continue
        d = g.nodes[n]
        if d.get("type") not in ("method", "entry"):
            continue
        roots.append(n)
    return sorted(roots)[:max_n]


def _first_n_graph_symbol_ids(g: CodeflowGraph, max_n: int) -> list[str]:
    ids = sorted(
        n for n in g.nodes() if isinstance(n, str) and "::" in n and not n.startswith("unknown::")
    )
    return ids[:max_n]


def _resolve_scan_entry_ids(cfg: ScanConfig, g: CodeflowGraph, all_entries: list[EntryRecord]) -> tuple[list[str], list[str]]:
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
    g: CodeflowGraph,
    entry_ids: list[str],
    emitted_slugs: int,
    warnings: list[str],
    cfg: ScanConfig,
    pr_impact: dict[str, Any] | None = None,
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
        f"- **cfg_probability:** {cfg.cfg_probability}",
        f"- **cfg_mermaid_probabilities:** {cfg.cfg_mermaid_probabilities}",
        f"- **cfg_runtime_trace:** {str(cfg.cfg_runtime_trace) if cfg.cfg_runtime_trace else 'None'}",
        f"- **cfg_loop_repeat_prob:** {cfg.cfg_loop_repeat_prob}",
        f"- **graph_include_structural:** {cfg.graph_include_structural}",
        f"- **enable_dependency_graph:** {cfg.enable_dependency_graph}",
        f"- **structural_graph_enabled:** {cfg.structural_graph_enabled()}",
        f"- **parser_mode:** `{cfg.parser_mode}`",
        f"- **ui_cfg_max_methods:** {cfg.ui_cfg_max_methods}",
        f"- **intelligence_transitive_callers:** {cfg.intelligence_transitive_callers}",
        f"- **emit_system_graph_stats:** {cfg.emit_system_graph_stats}",
        f"- **emit_graph_sqlite:** {cfg.emit_graph_sqlite}",
        f"- **emit_graph_communities:** {cfg.emit_graph_communities}",
        f"- **include_references:** {cfg.include_references}",
        f"- **include_events:** {cfg.include_events}",
        f"- **cluster_mode:** `{cfg.cluster_mode}`",
        f"- **graph_query:** {repr(cfg.graph_query) if cfg.graph_query else 'None'}",
        f"- **emit_llm_entry_sidecar:** {cfg.emit_llm_entry_sidecar}",
        f"- **enable_embeddings:** {cfg.enable_embeddings}",
        f"- **embedding_model:** `{cfg.embedding_model}`",
        f"- **semantic_top_k:** {cfg.semantic_top_k}",
        f"- **emit_html_unified:** {cfg.emit_html_unified}",
        f"- **nl_query:** {repr(cfg.nl_query) if cfg.nl_query else 'None'}",
        f"- **emit_runtime_insights:** {cfg.emit_runtime_insights}",
        f"- **runtime_insight_frequency_threshold:** {cfg.runtime_insight_frequency_threshold}",
        f"- **runtime_insight_hot_paths_top:** {cfg.runtime_insight_hot_paths_top}",
        f"- **multi_repo_roots:** {len(cfg.multi_repo_roots)} extra root(s)",
        f"- **diff_base / diff_head:** {repr(cfg.diff_base) if cfg.diff_base else 'None'} / {repr(cfg.diff_head) if cfg.diff_head else 'None'}",
        "",
    ]
    if pr_impact:
        sample_seeds = pr_impact.get("seed_nodes") or []
        if isinstance(sample_seeds, list):
            seed_preview = ", ".join(f"`{x}`" for x in sample_seeds[:8])
        else:
            seed_preview = ""
        lines += [
            "## PR impact",
            "",
            f"- **base → head:** `{pr_impact.get('base')}` → `{pr_impact.get('head')}`",
            f"- **Changed files:** {pr_impact.get('changed_files_count', 0)}",
            f"- **Seed nodes (files touched):** {pr_impact.get('seed_nodes_count', 0)}",
            f"- **Impacted nodes (downstream reachability):** {pr_impact.get('impacted_nodes_count', 0)}",
        ]
        if seed_preview:
            lines.append(f"- **Sample seeds:** {seed_preview}")
        lines.append("")
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
    if cfg.enable_embeddings:
        lines.append(
            "**Semantic layer:** with `--enable-embeddings` and `mdengine[codeflow-semantic]`, vectors are cached under "
            "`.codeflow_cache/semantic/`. First model download may require network (`HF_HOME`). "
            "`semantic-manifest.json`, optional `semantic-search-results.json`, and per-entry `semantic-neighbors.json` "
            "are written when embeddings succeed.",
        )
    else:
        lines.append(
            "**Hybrid signals (no embeddings):** per-entry CFG path enumeration when `--emit-cfg` is on; "
            "Markdown *Called by* / *Impact* use dependency reachability (calls + structural edges; CONTAINS excluded); "
            "`graph-communities.json` / `graph.db` when those flags are enabled. "
            "Enable `--enable-embeddings` for local SentenceTransformer similarity and semantic/hybrid clustering.",
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _graph_and_parse_for_scan(
    cfg: ScanConfig,
    workspace: LoadedWorkspace | None,
) -> tuple[CodeflowGraph, list[FileParseResult], LoadedWorkspace, str | None]:
    """Return merged graph, combined parse results, primary workspace, and primary repo label (if multi-repo)."""
    roots = [cfg.project_root.resolve(), *[Path(p).resolve() for p in cfg.multi_repo_roots]]
    if len(roots) == 1:
        ws_main = workspace or LoadedWorkspace(root=roots[0], cleanup_dir=None)
        parse_results = _parse_results_for_workspace(ws_main, cfg)
        enrich_parse_results_with_ir(parse_results, cfg, ws_main.root)
        gb: GraphBuildResult = build_graph(
            parse_results,
            ws_main.root,
            include_structural=cfg.structural_graph_enabled(),
            include_references=cfg.include_references,
        )
        g = gb.graph
        if cfg.include_events:
            apply_event_edges(g, parse_results)
        return g, parse_results, ws_main, None

    used: set[str] = set()
    labels: list[str] = []
    graphs: list[CodeflowGraph] = []
    all_parse: list[FileParseResult] = []
    ws_main = workspace or LoadedWorkspace(root=roots[0], cleanup_dir=None)
    for i, root in enumerate(roots):
        lab = repo_label(root, i, used)
        labels.append(lab)
        ws_i = ws_main if i == 0 else LoadedWorkspace(root=root, cleanup_dir=None)
        try:
            pr_i = _parse_results_for_workspace(ws_i, cfg)
            enrich_parse_results_with_ir(pr_i, cfg, root)
            gb_i = build_graph(
                pr_i,
                root,
                include_structural=cfg.structural_graph_enabled(),
                include_references=cfg.include_references,
            )
            g_i = gb_i.graph
            if cfg.include_events:
                apply_event_edges(g_i, pr_i)
            prefix_parse_results(pr_i, lab)
            graphs.append(g_i)
            all_parse.extend(pr_i)
        finally:
            if i > 0:
                ws_i.close()
    g_m = merge_graphs(graphs, labels)
    if cfg.resolve_cross_repo:
        from md_generator.codeflow.graph.cross_repo_resolver import resolve_cross_repo_imports

        resolve_cross_repo_imports(g_m, cfg.cross_repo_package_hints)
    else:
        link_cross_repo_imports(g_m, package_hints=cfg.cross_repo_package_hints)
    return g_m, all_parse, ws_main, labels[0]


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
        pr = parse_source_file(reg, p, ws.root, lang, cfg.parser_mode)
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

    if cfg.cache_clear_mode and str(cfg.cache_clear_mode).strip():
        from md_generator.codeflow.core.cache_manager import apply_project_cache_clear

        apply_project_cache_clear(cfg.project_root.resolve(), str(cfg.cache_clear_mode).strip())

    g, parse_results, ws, primary_repo_label = _graph_and_parse_for_scan(cfg, workspace)

    semantic_artifacts = None
    scan_semantic_warnings: list[str] = []
    if cfg.enable_embeddings:
        try:
            from md_generator.codeflow.graph.semantic_enricher import attach_semantic_groups, build_semantic_artifacts

            semantic_artifacts = build_semantic_artifacts(
                g,
                ws.root,
                model_id=cfg.embedding_model,
                max_nodes=cfg.embedding_max_nodes,
                k_semantic=cfg.embedding_k_clusters,
            )
            if semantic_artifacts:
                attach_semantic_groups(g, semantic_artifacts.labels)
            else:
                scan_semantic_warnings.append(
                    "enable_embeddings: fewer than 2 embeddable method/entry nodes; semantic artifacts skipped.",
                )
        except ImportError as e:
            scan_semantic_warnings.append(
                f"enable_embeddings requires optional extra mdengine[codeflow-semantic] ({e}).",
            )

    out = cfg.output_path
    out.mkdir(parents=True, exist_ok=True)

    scan_warnings_pre: list[str] = []
    pr_impact_payload: dict[str, Any] | None = None
    pr_seeds: set[str] | None = None
    pr_impacted: set[str] | None = None
    if (cfg.diff_base and not cfg.diff_head) or (cfg.diff_head and not cfg.diff_base):
        scan_warnings_pre.append("PR impact: set both diff_base and diff_head, or omit both.")
    elif cfg.diff_base and cfg.diff_head:
        try:
            changed = git_changed_files(cfg.project_root.resolve(), cfg.diff_base, cfg.diff_head)
            pr_seeds = nodes_touching_files(g, set(changed), primary_repo_label=primary_repo_label)
            pr_impacted = diff_impact_nodes(g, pr_seeds)
            pr_impact_payload = {
                "base": cfg.diff_base,
                "head": cfg.diff_head,
                "changed_files": sorted(changed)[:PR_IMPACT_LIST_CAP],
                "changed_files_count": len(changed),
                "seed_nodes": sorted(pr_seeds)[:PR_IMPACT_LIST_CAP],
                "seed_nodes_count": len(pr_seeds),
                "impacted_nodes": sorted(pr_impacted)[:PR_IMPACT_LIST_CAP],
                "impacted_nodes_count": len(pr_impacted),
            }
            (out / "pr-impact.json").write_text(json.dumps(pr_impact_payload, indent=2), encoding="utf-8")
        except DiffAnalysisError as e:
            scan_warnings_pre.append(f"PR impact (git diff): {e}")

    all_entries = [e for pr in parse_results for e in pr.entries]
    entry_ids, scan_warnings = _resolve_scan_entry_ids(cfg, g, all_entries)
    scan_warnings = scan_warnings_pre + scan_warnings
    scan_warnings.extend(scan_semantic_warnings)

    fmts = {x.strip().lower() for x in cfg.formats}

    cluster_by_file: dict[str, int] | None = None
    comm_payload: list[Any] | None = None
    comm_algo: str | None = None
    if cfg.emit_graph_communities or "md" in fmts:
        sem_labs = None
        if semantic_artifacts and cfg.cluster_mode in ("semantic", "hybrid"):
            sem_labs = semantic_artifacts.labels
        comm_payload, comm_algo = communities_for_mode(
            g,
            cfg.cluster_mode,
            semantic_labels=sem_labs,
            k_semantic=cfg.embedding_k_clusters,
        )
        if comm_payload and "md" in fmts:
            cluster_by_file = file_cluster_labels(g, comm_payload, cfg.cluster_mode)

    search_hits_list: list[dict[str, Any]] | None = None
    if semantic_artifacts:
        (out / "semantic-manifest.json").write_text(
            json.dumps(
                {
                    "model_id": semantic_artifacts.model_id,
                    "embedded_node_count": len(semantic_artifacts.node_ids),
                    "k_clusters": cfg.embedding_k_clusters,
                    "algorithm": "sentence_transformers + sklearn_kmeans + cosine_index",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        q = (cfg.semantic_search or "").strip()
        if q:
            from md_generator.codeflow.api.semantic_api import search_similar_serializable

            search_hits_list = search_similar_serializable(
                semantic_artifacts,
                q,
                cfg.semantic_top_k,
                g,
            )
            (out / "semantic-search-results.json").write_text(
                json.dumps({"query": q, "hits": search_hits_list}, indent=2),
                encoding="utf-8",
            )

    entry_ids = sort_entry_ids(entry_ids, g, all_entries)
    entry_by_symbol = {e.symbol_id: e for e in all_entries}
    cluster_mode_note = f"{cfg.cluster_mode} ({comm_algo or 'n/a'})"

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

    runtime_trace_obj: dict[str, Any] | None = None
    if cfg.emit_cfg and cfg.emit_runtime_insights and cfg.cfg_runtime_trace and cfg.cfg_runtime_trace.is_file():
        try:
            _tr = json.loads(cfg.cfg_runtime_trace.read_text(encoding="utf-8"))
            if isinstance(_tr, dict):
                runtime_trace_obj = _tr
        except (OSError, json.JSONDecodeError):
            runtime_trace_obj = None

    if cfg.emit_runtime_insights:
        if not cfg.emit_cfg:
            scan_warnings.append("emit_runtime_insights requires --emit-cfg.")
        elif not cfg.cfg_runtime_trace or not cfg.cfg_runtime_trace.is_file():
            scan_warnings.append("emit_runtime_insights requires --cfg-runtime-trace pointing to a JSON file.")
        elif runtime_trace_obj is None:
            scan_warnings.append("emit_runtime_insights: could not load or parse runtime trace JSON.")

    if cfg.nl_query and str(cfg.nl_query).strip():
        from md_generator.codeflow.graph.nl_query import execute_nl_intent, parse_nl_query

        _nq = str(cfg.nl_query).strip()
        _parsed = parse_nl_query(_nq)
        _nqr = execute_nl_intent(
            g,
            _parsed,
            semantic_artifacts=semantic_artifacts,
            top_k=cfg.semantic_top_k,
            list_cap=cfg.intelligence_list_cap,
        )
        (out / "nl-query-results.json").write_text(
            json.dumps({"query": _nq, "parsed": dict(_parsed), "result": _nqr}, indent=2),
            encoding="utf-8",
        )

    for eid in entry_ids:
        if include_map:
            ndata = dict(g.nodes[eid]) if eid in g else {}
            ek = ndata.get("entry_kind")
            if ek and ek not in include_map:
                continue
        emitted_slugs += 1
        sl = slice_from_entry(g, eid, cfg.depth, relations=cfg.flow_slice_relations())
        slug = _slug(eid)
        sub = entry_base / slug
        sub.mkdir(parents=True, exist_ok=True)
        rec = entry_by_symbol.get(eid)
        neighbor_rows: list[dict[str, Any]] | None = None
        neigh_wrap: dict[str, Any] | None = None
        if semantic_artifacts:
            from md_generator.codeflow.api.semantic_api import neighbors_serializable

            neighbor_rows = neighbors_serializable(semantic_artifacts, eid, cfg.semantic_top_k, g)
            neigh_wrap = {"entry_id": eid, "top_k": neighbor_rows}
            (sub / "semantic-neighbors.json").write_text(json.dumps(neigh_wrap, indent=2), encoding="utf-8")
        semantic_search_href: str | None = None
        if (out / "semantic-search-results.json").is_file():
            semantic_search_href = os.path.relpath(out / "semantic-search-results.json", sub).replace("\\", "/")
        nl_query_href: str | None = None
        if (out / "nl-query-results.json").is_file():
            nl_query_href = os.path.relpath(out / "nl-query-results.json", sub).replace("\\", "/")
        runtime_insights_payload: dict[str, Any] | None = None
        rules = None
        if "md" in fmts:
            write_flow_markdown(
                sub / "flow.md",
                eid,
                sl,
                g,
                list_cap=cfg.intelligence_list_cap,
                intelligence_transitive_callers=cfg.intelligence_transitive_callers,
                graph_include_structural=cfg.structural_graph_enabled(),
            )
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
                from md_generator.codeflow.graph.path_probability import PathProbConfig, score_paths
                from md_generator.codeflow.graph.runtime_integration import apply_runtime_weights
                from md_generator.codeflow.generators.cfg_paths_markdown import paths_to_markdown
                from md_generator.codeflow.generators.cfg_render import cfg_to_markdown_section, write_cfg_paths_sidecars, write_cfg_sidecar

                c = build_cfg_from_ir(ir_m, max_nodes=cfg.cfg_max_nodes)
                c = expand_cfg_calls(
                    c,
                    method_cfgs_for_cfg or {},
                    max_call_depth=cfg.cfg_call_depth,
                    inline_calls=cfg.cfg_inline_calls,
                )
                if cfg.cfg_runtime_trace and cfg.cfg_runtime_trace.is_file():
                    try:
                        trace_obj = json.loads(cfg.cfg_runtime_trace.read_text(encoding="utf-8"))
                        if isinstance(trace_obj, dict):
                            apply_runtime_weights(c, trace_obj)
                    except (OSError, json.JSONDecodeError):
                        pass
                prob_conf = PathProbConfig(loop_repeat=max(0.01, min(0.99, float(cfg.cfg_loop_repeat_prob))))
                write_cfg_sidecar(
                    sub,
                    c,
                    mermaid_show_probability=cfg.cfg_mermaid_probabilities,
                    prob_config=prob_conf,
                )
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
                path_probs: list[float] | None = None
                if cfg.cfg_probability and path_res.paths:
                    path_probs = [pr for _p, pr in score_paths(c, path_res.paths, prob_conf)]
                write_cfg_paths_sidecars(
                    sub,
                    c,
                    path_res.paths,
                    truncated=path_res.truncated,
                    path_probabilities=path_probs,
                )
                if cfg.emit_runtime_insights and runtime_trace_obj is not None:
                    from md_generator.codeflow.graph.anomaly import runtime_anomalies_payload, semantic_outlier_nodes
                    from md_generator.codeflow.graph.hotpath import hot_paths_payload

                    hp = hot_paths_payload(
                        c,
                        path_res.paths,
                        runtime_trace_obj,
                        top_n=cfg.runtime_insight_hot_paths_top,
                        path_truncated=path_res.truncated,
                    )
                    an = runtime_anomalies_payload(
                        c,
                        runtime_trace_obj,
                        frequency_threshold=cfg.runtime_insight_frequency_threshold,
                    )
                    runtime_insights_payload = {**hp, **an}
                    if semantic_artifacts:
                        runtime_insights_payload["semantic_outliers"] = semantic_outlier_nodes(
                            semantic_artifacts,
                            distance_threshold=cfg.semantic_outlier_distance_threshold,
                        )
                    (sub / "runtime-insights.json").write_text(
                        json.dumps(runtime_insights_payload, indent=2),
                        encoding="utf-8",
                    )
                if "md" in fmts:
                    flow_path = sub / "flow.md"
                    extra = (
                        cfg_to_markdown_section(
                            c,
                            mermaid_show_probability=cfg.cfg_mermaid_probabilities,
                            prob_config=prob_conf,
                        )
                        + "\n"
                        + paths_to_markdown(
                            c,
                            path_res.paths,
                            c.nodes,
                            truncated=path_res.truncated,
                            path_probabilities=path_probs,
                        )
                    )
                    flow_path.write_text(flow_path.read_text(encoding="utf-8") + "\n" + extra, encoding="utf-8")
        if "md" in fmts:
            pr_slice: dict[str, Any] | None = None
            if pr_seeds is not None and pr_impacted is not None and pr_impact_payload:
                n_sl = set(sl.nodes)
                pr_slice = {
                    "base": pr_impact_payload["base"],
                    "head": pr_impact_payload["head"],
                    "changed_files_count": pr_impact_payload["changed_files_count"],
                    "impacted_nodes_count": pr_impact_payload["impacted_nodes_count"],
                    "seeds_in_slice_count": len(pr_seeds & n_sl),
                    "seed_sample": sorted(pr_seeds & n_sl)[:10],
                    "impacted_in_slice_count": len(pr_impacted & n_sl),
                }
            write_entry_markdown(
                sub / "entry.md",
                eid,
                sl,
                g,
                rec,
                rules=rules,
                intelligence_cap=cfg.intelligence_list_cap,
                graph_include_structural=cfg.structural_graph_enabled(),
                intelligence_transitive_callers=cfg.intelligence_transitive_callers,
                include_references=cfg.include_references,
                include_events=cfg.include_events,
                event_impact_section=cfg.event_impact,
                cluster_by_file=cluster_by_file,
                enable_embeddings=cfg.enable_embeddings,
                semantic_neighbors=neighbor_rows,
                nl_query_href=nl_query_href,
                runtime_insights=runtime_insights_payload,
                pr_impact_slice=pr_slice,
            )
            if cfg.business_rules and cfg.business_rules_combined and rules is not None:
                write_combined_entry_markdown(
                    sub / "entry.md",
                    sub / "business_rules.md",
                    sub / "entry.combined.md",
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
        if cfg.emit_html_unified:
            from md_generator.codeflow.generators.html_unified import write_html_unified

            sub_gu = g.subgraph(sl.nodes).copy()
            slice_json = graph_to_serializable(sub_gu)
            cfg_mmd_u: str | None = None
            pm_u = sub / "cfg.mmd"
            if pm_u.is_file():
                cfg_mmd_u = pm_u.read_text(encoding="utf-8", errors="replace")
            pr_html: dict[str, Any] | None = None
            if pr_seeds is not None and pr_impacted is not None:
                n_sl = set(sl.nodes)
                pr_html = {
                    "seed_nodes": sorted(pr_seeds & n_sl)[:300],
                    "impacted_nodes": sorted(pr_impacted & n_sl)[:800],
                }
            cfg_bundle: dict[str, dict[str, str]] = {}
            if cfg.emit_cfg and cfg.emit_html_unified:
                cfg_bundle = _build_cfg_mermaid_bundle_for_slice(set(sl.nodes), parse_results, cfg, method_cfgs_for_cfg)
            write_html_unified(
                sub,
                eid,
                sl,
                slice_json,
                cfg_mermaid_text=cfg_mmd_u,
                semantic_neighbors=neigh_wrap,
                search_hits=search_hits_list,
                cluster_mode_note=cluster_mode_note,
                semantic_search_results_href=semantic_search_href,
                nl_query_href=nl_query_href,
                runtime_insights=runtime_insights_payload,
                pr_impact=pr_html,
                cfg_by_symbol=cfg_bundle or None,
                file_cluster_map=cluster_by_file,
            )

    if "json" in fmts:
        full = graph_to_serializable(g)
        (out / "graph-full.json").write_text(json.dumps(full, indent=2), encoding="utf-8")
        if cfg.emit_graph_schema:
            sch = to_stable_schema(g)
            (out / "graph-schema.json").write_text(json.dumps(sch, indent=2), encoding="utf-8")
        if cfg.emit_graph_communities and comm_payload is not None:
            body: dict[str, Any] = {
                "algorithm": comm_algo or "unknown",
                "layer": cfg.cluster_mode,
                "communities": comm_payload,
            }
            (out / "graph-communities.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
        if cfg.graph_query and cfg.graph_query.strip():
            rows = execute_query(g, cfg.graph_query.strip())
            (out / "query-results.json").write_text(
                json.dumps({"query": cfg.graph_query.strip(), "rows": rows}, indent=2),
                encoding="utf-8",
            )
    if cfg.emit_graph_sqlite:
        from md_generator.codeflow.graph.sqlite_export import export_graph_sqlite

        export_graph_sqlite(out / "graph.db", g)

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
            pr_impact=pr_impact_payload,
        )

    return out


def _build_cfg_mermaid_bundle_for_slice(
    slice_nodes: set[str],
    parse_results: list[FileParseResult],
    cfg: ScanConfig,
    method_cfgs_for_cfg: dict[str, Any] | None,
) -> dict[str, dict[str, str]]:
    """Precompute Mermaid CFG text per method symbol in the slice (for static unified HTML)."""
    if not cfg.emit_cfg:
        return {}
    from md_generator.codeflow.graph.call_expander import expand_cfg_calls
    from md_generator.codeflow.graph.cfg_builder import build_cfg_from_ir
    from md_generator.codeflow.generators.cfg_render import cfg_to_mermaid
    from md_generator.codeflow.graph.path_probability import PathProbConfig

    out: dict[str, dict[str, str]] = {}
    prob_conf = PathProbConfig(loop_repeat=max(0.01, min(0.99, float(cfg.cfg_loop_repeat_prob))))
    n = 0
    for nid in sorted(slice_nodes, key=str):
        if n >= cfg.ui_cfg_max_methods:
            break
        sid = str(nid)
        ir_m = _lookup_ir_method(sid, parse_results)
        if ir_m is None:
            continue
        c = build_cfg_from_ir(ir_m, max_nodes=cfg.cfg_max_nodes)
        c = expand_cfg_calls(
            c,
            method_cfgs_for_cfg or {},
            max_call_depth=cfg.cfg_call_depth,
            inline_calls=cfg.cfg_inline_calls,
        )
        mmd = cfg_to_mermaid(
            c,
            show_edge_probability=cfg.cfg_mermaid_probabilities,
            prob_config=prob_conf,
        )
        out[sid] = {"mermaid": mmd}
        n += 1
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
    from dataclasses import replace

    td = Path(tempfile.mkdtemp(prefix="codeflow-scan-"))
    try:
        root = workspace_root or cfg.project_root
        wc = LoadedWorkspace(root=root.resolve(), cleanup_dir=None)
        cfg2 = replace(cfg, project_root=root.resolve(), output_path=td / "out")
        run_scan(cfg2, workspace=wc)
        buf = td / "bundle.zip"
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in (td / "out").rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(td).as_posix())
        return buf.read_bytes()
    finally:
        shutil.rmtree(td, ignore_errors=True)
