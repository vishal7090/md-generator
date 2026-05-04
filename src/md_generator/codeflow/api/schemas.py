from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from md_generator.codeflow.core.run_config import ScanConfig


class AnalyzeOptions(BaseModel):
    formats: str | None = Field(default=None, description="Comma-separated: md,html,mermaid,json")
    depth: int = 5
    languages: str = "mixed"
    entry: str | None = None
    include: str | None = None
    exclude: str | None = None
    business_rules: bool | None = Field(default=None, description="If set, enable/disable business rule MD")
    business_rules_sql: bool | None = Field(default=None, description="If true, scan *.sql for triggers")
    business_rules_combined: bool | None = Field(default=None, description="If set, control entry.combined.md")
    entry_fallback: Literal["none", "roots", "first_n"] | None = Field(
        default=None,
        description="none | roots | first_n when no detected entries",
    )
    entry_fallback_max: int | None = None
    emit_entry_per_method: bool | None = None
    emit_entry_max: int | None = None
    emit_entry_filter: str | None = None
    entries_file: str | None = Field(default=None, description="Path to file of symbol ids (workspace-relative or absolute)")
    write_scan_summary: bool | None = Field(default=None, description="If false, skip scan-summary.md")
    liferay_portlet_base_classes: str | None = Field(
        default=None,
        description="Comma-separated extra portlet superclass simple names",
    )
    codeflow_config_path: str | None = Field(default=None, description="Path to codeflow.yaml")
    emit_flow_tree_json: bool | None = None
    verbose: bool | None = None
    emit_graph_schema: bool | None = None
    intelligence_list_cap: int | None = None
    emit_cfg: bool | None = None
    cfg_max_nodes: int | None = None
    cfg_inline_calls: bool | None = None
    cfg_call_depth: int | None = None
    cfg_max_paths: int | None = None
    cfg_path_max_depth: int | None = None
    cfg_loop_visits: int | None = None
    graph_include_structural: bool | None = None
    intelligence_transitive_callers: bool | None = None
    emit_system_graph_stats: bool | None = None
    emit_llm_entry_sidecar: bool | None = None


def options_to_scan_config(workspace_src: Path, output_subdir: str, raw: AnalyzeOptions | None) -> ScanConfig:
    fmts = ("md", "mermaid", "json")
    if raw and raw.formats:
        fmts = tuple(x.strip().lower() for x in raw.formats.split(",") if x.strip())
    entry_list = None
    if raw and raw.entry:
        entry_list = [x.strip() for x in raw.entry.split(",") if x.strip()]
    br = True if not raw or raw.business_rules is None else raw.business_rules
    br_sql = False if not raw or raw.business_rules_sql is None else raw.business_rules_sql
    br_comb = True if not raw or raw.business_rules_combined is None else raw.business_rules_combined
    ef = "roots" if not raw or raw.entry_fallback is None else raw.entry_fallback
    efm = 20 if not raw or raw.entry_fallback_max is None else int(raw.entry_fallback_max)
    epm = False if not raw or raw.emit_entry_per_method is None else bool(raw.emit_entry_per_method)
    emx = None if not raw else raw.emit_entry_max
    efilt = None if not raw else raw.emit_entry_filter
    efpath = None
    if raw and raw.entries_file:
        efpath = Path(raw.entries_file)
        if not efpath.is_absolute():
            efpath = (workspace_src / efpath).resolve()
        else:
            efpath = efpath.resolve()
    wss = True if not raw or raw.write_scan_summary is None else bool(raw.write_scan_summary)
    lpbc: tuple[str, ...] = ()
    if raw and raw.liferay_portlet_base_classes and str(raw.liferay_portlet_base_classes).strip():
        lpbc = tuple(x.strip() for x in str(raw.liferay_portlet_base_classes).split(",") if x.strip())
    ccpath = None
    if raw and raw.codeflow_config_path and str(raw.codeflow_config_path).strip():
        p = Path(raw.codeflow_config_path.strip())
        ccpath = p if p.is_absolute() else (workspace_src / p).resolve()
    eftj = False if not raw or raw.emit_flow_tree_json is None else bool(raw.emit_flow_tree_json)
    verb = False if not raw or raw.verbose is None else bool(raw.verbose)
    egs = False if not raw or raw.emit_graph_schema is None else bool(raw.emit_graph_schema)
    ilc = 80 if not raw or raw.intelligence_list_cap is None else int(raw.intelligence_list_cap)
    ecfg = False if not raw or raw.emit_cfg is None else bool(raw.emit_cfg)
    cmn = 500 if not raw or raw.cfg_max_nodes is None else int(raw.cfg_max_nodes)
    cic = False if not raw or raw.cfg_inline_calls is None else bool(raw.cfg_inline_calls)
    ccd = 3 if not raw or raw.cfg_call_depth is None else int(raw.cfg_call_depth)
    cmpaths = 100 if not raw or raw.cfg_max_paths is None else int(raw.cfg_max_paths)
    cpmd = 1000 if not raw or raw.cfg_path_max_depth is None else int(raw.cfg_path_max_depth)
    clv = 2 if not raw or raw.cfg_loop_visits is None else int(raw.cfg_loop_visits)
    gis = False if not raw or raw.graph_include_structural is None else bool(raw.graph_include_structural)
    itc = False if not raw or raw.intelligence_transitive_callers is None else bool(raw.intelligence_transitive_callers)
    esgs = False if not raw or raw.emit_system_graph_stats is None else bool(raw.emit_system_graph_stats)
    ellm = False if not raw or raw.emit_llm_entry_sidecar is None else bool(raw.emit_llm_entry_sidecar)
    return ScanConfig(
        project_root=workspace_src,
        output_path=workspace_src.parent / output_subdir,
        formats=fmts,
        depth=(raw.depth if raw else 5),
        languages=(raw.languages if raw else "mixed"),
        entry=entry_list,
        include=raw.include if raw else None,
        exclude=raw.exclude if raw else None,
        business_rules=br,
        business_rules_sql=br_sql,
        business_rules_combined=br_comb,
        entry_fallback=ef,  # type: ignore[arg-type]
        entry_fallback_max=efm,
        emit_entry_per_method=epm,
        emit_entry_max=emx,
        emit_entry_filter=efilt,
        entries_file=efpath,
        write_scan_summary=wss,
        liferay_portlet_base_classes=lpbc,
        codeflow_config_path=ccpath,
        emit_flow_tree_json=eftj,
        verbose=verb,
        emit_graph_schema=egs,
        intelligence_list_cap=ilc,
        emit_cfg=ecfg,
        cfg_max_nodes=cmn,
        cfg_inline_calls=cic,
        cfg_call_depth=ccd,
        cfg_max_paths=cmpaths,
        cfg_path_max_depth=cpmd,
        cfg_loop_visits=clv,
        graph_include_structural=gis,
        intelligence_transitive_callers=itc,
        emit_system_graph_stats=esgs,
        emit_llm_entry_sidecar=ellm,
    )


def merge_upload_options_json(options_json: str | None) -> AnalyzeOptions | None:
    if not options_json:
        return None
    data = json.loads(options_json)
    return AnalyzeOptions.model_validate(data)


def scan_config_dump(cfg: ScanConfig) -> dict[str, Any]:
    return {
        "project_root": str(cfg.project_root),
        "output_path": str(cfg.output_path),
        "paths_override": [str(p) for p in cfg.paths_override] if cfg.paths_override else None,
        "formats": list(cfg.formats),
        "depth": cfg.depth,
        "languages": cfg.languages,
        "entry": cfg.entry,
        "include": cfg.include,
        "exclude": cfg.exclude,
        "include_internal": cfg.include_internal,
        "async_mode": cfg.async_mode,
        "jobs": cfg.jobs,
        "runtime": cfg.runtime,
        "business_rules": cfg.business_rules,
        "business_rules_sql": cfg.business_rules_sql,
        "business_rules_combined": cfg.business_rules_combined,
        "entry_fallback": cfg.entry_fallback,
        "entry_fallback_max": cfg.entry_fallback_max,
        "emit_entry_per_method": cfg.emit_entry_per_method,
        "emit_entry_max": cfg.emit_entry_max,
        "emit_entry_filter": cfg.emit_entry_filter,
        "entries_file": str(cfg.entries_file) if cfg.entries_file else None,
        "write_scan_summary": cfg.write_scan_summary,
        "liferay_portlet_base_classes": list(cfg.liferay_portlet_base_classes),
        "codeflow_config_path": str(cfg.codeflow_config_path) if cfg.codeflow_config_path else None,
        "emit_flow_tree_json": cfg.emit_flow_tree_json,
        "verbose": cfg.verbose,
        "emit_graph_schema": cfg.emit_graph_schema,
        "intelligence_list_cap": cfg.intelligence_list_cap,
        "emit_cfg": cfg.emit_cfg,
        "cfg_max_nodes": cfg.cfg_max_nodes,
        "cfg_inline_calls": cfg.cfg_inline_calls,
        "cfg_call_depth": cfg.cfg_call_depth,
        "cfg_max_paths": cfg.cfg_max_paths,
        "cfg_path_max_depth": cfg.cfg_path_max_depth,
        "cfg_loop_visits": cfg.cfg_loop_visits,
        "graph_include_structural": cfg.graph_include_structural,
        "intelligence_transitive_callers": cfg.intelligence_transitive_callers,
        "emit_system_graph_stats": cfg.emit_system_graph_stats,
        "emit_llm_entry_sidecar": cfg.emit_llm_entry_sidecar,
    }


def scan_config_load(data: dict[str, Any]) -> ScanConfig:
    po = data.get("paths_override")
    return ScanConfig(
        project_root=Path(data["project_root"]),
        output_path=Path(data["output_path"]),
        paths_override=[Path(p) for p in po] if po else None,
        formats=tuple(data.get("formats") or ("md", "mermaid", "json")),
        depth=int(data.get("depth", 5)),
        languages=str(data.get("languages", "mixed")),
        entry=list(data["entry"]) if data.get("entry") else None,
        include=data.get("include"),
        exclude=data.get("exclude"),
        include_internal=bool(data.get("include_internal", True)),
        async_mode=bool(data.get("async_mode", True)),
        jobs=bool(data.get("jobs", False)),
        runtime=bool(data.get("runtime", False)),
        business_rules=bool(data.get("business_rules", True)),
        business_rules_sql=bool(data.get("business_rules_sql", False)),
        business_rules_combined=bool(data.get("business_rules_combined", True)),
        entry_fallback=data.get("entry_fallback", "roots"),  # type: ignore[arg-type]
        entry_fallback_max=int(data.get("entry_fallback_max", 20)),
        emit_entry_per_method=bool(data.get("emit_entry_per_method", False)),
        emit_entry_max=data.get("emit_entry_max"),
        emit_entry_filter=data.get("emit_entry_filter"),
        entries_file=Path(data["entries_file"]) if data.get("entries_file") else None,
        write_scan_summary=bool(data.get("write_scan_summary", True)),
        liferay_portlet_base_classes=_load_liferay_bases(data.get("liferay_portlet_base_classes")),
        codeflow_config_path=Path(data["codeflow_config_path"]) if data.get("codeflow_config_path") else None,
        emit_flow_tree_json=bool(data.get("emit_flow_tree_json", False)),
        verbose=bool(data.get("verbose", False)),
        emit_graph_schema=bool(data.get("emit_graph_schema", False)),
        intelligence_list_cap=int(data.get("intelligence_list_cap", 80)),
        emit_cfg=bool(data.get("emit_cfg", False)),
        cfg_max_nodes=int(data.get("cfg_max_nodes", 500)),
        cfg_inline_calls=bool(data.get("cfg_inline_calls", False)),
        cfg_call_depth=int(data.get("cfg_call_depth", 3)),
        cfg_max_paths=int(data.get("cfg_max_paths", 100)),
        cfg_path_max_depth=int(data.get("cfg_path_max_depth", 1000)),
        cfg_loop_visits=int(data.get("cfg_loop_visits", 2)),
        graph_include_structural=bool(data.get("graph_include_structural", False)),
        intelligence_transitive_callers=bool(data.get("intelligence_transitive_callers", False)),
        emit_system_graph_stats=bool(data.get("emit_system_graph_stats", False)),
        emit_llm_entry_sidecar=bool(data.get("emit_llm_entry_sidecar", False)),
    )


def _load_liferay_bases(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, list):
        return tuple(str(x).strip() for x in raw if str(x).strip())
    if isinstance(raw, str):
        return tuple(x.strip() for x in raw.split(",") if x.strip())
    return ()
