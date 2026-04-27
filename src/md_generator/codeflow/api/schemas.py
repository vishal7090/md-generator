from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    )
