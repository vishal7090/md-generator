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
    )
