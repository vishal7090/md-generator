from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from md_generator.db.core.models import FEATURES

ALLOWED_ERD_SCOPES = frozenset({"full", "per_schema", "per_table"})
ALLOWED_README_FEATURE_MERGE = frozenset({"none", "inline", "toc"})


@dataclass
class ErdConfig:
    """Graphviz ERD settings (see default.yaml `erd`)."""

    max_tables: int = 100
    scope: str = "full"

    def normalized(self) -> ErdConfig:
        s = (self.scope or "full").lower().strip()
        if s not in ALLOWED_ERD_SCOPES:
            s = "full"
        mt = max(1, min(int(self.max_tables), 100_000))
        return ErdConfig(max_tables=mt, scope=s)


@dataclass
class RunConfig:
    db_type: str
    uri: str
    schema: str | None = None
    database: str | None = None
    output_path: Path = field(default_factory=lambda: Path("docs"))
    split_files: bool = True
    include: frozenset[str] = field(default_factory=lambda: frozenset(FEATURES))
    exclude: frozenset[str] = field(default_factory=frozenset)
    workers: int = 4
    limits: dict[str, Any] = field(default_factory=dict)
    erd: ErdConfig = field(default_factory=ErdConfig)
    write_combined_feature_markdown: bool = False
    readme_feature_merge: str = "none"  # none | inline | toc

    def with_output(self, path: Path) -> RunConfig:
        return replace(self, output_path=path)

    def effective_features(self) -> frozenset[str]:
        return frozenset(f for f in self.include if f not in self.exclude)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_run_config(path: Path | None, overrides: dict[str, Any] | None = None) -> RunConfig:
    raw: dict[str, Any] = {}
    if path is not None and path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif path is None:
        try:
            import importlib.resources as ir

            txt = ir.files("md_generator.db.config").joinpath("default.yaml").read_text(encoding="utf-8")
            raw = yaml.safe_load(txt) or {}
        except Exception:
            raw = {}
    if overrides:
        raw = _deep_merge(raw, overrides)
    db = raw.get("database") or {}
    db_type = str(db.get("type", "")).lower()
    uri = str(db.get("uri", ""))
    if db_type in ("mysql", "mariadb") and uri:
        try:
            from sqlalchemy.engine.url import make_url

            nu = uri
            if nu.startswith("mysql://") and "+pymysql" not in nu:
                nu = nu.replace("mysql://", "mysql+pymysql://", 1)
            dbname = make_url(nu).database
            cur = db.get("schema")
            # Packaged default.yaml uses postgres `schema: public`; for MySQL use DB name from URI.
            if dbname and (cur is None or cur == "" or cur == "public"):
                db["schema"] = dbname
                raw["database"] = db
        except Exception:
            pass
    out = raw.get("output") or {}
    feats = raw.get("features") or {}
    exe = raw.get("execution") or {}
    lim = raw.get("limits") or {}
    erd_base: dict[str, Any] = {"max_tables": 100, "scope": "full"}
    if isinstance(raw.get("erd"), dict):
        erd_merged = _deep_merge(erd_base, raw["erd"])
    else:
        erd_merged = erd_base
    erd_cfg = ErdConfig(
        max_tables=int(erd_merged.get("max_tables", 100)),
        scope=str(erd_merged.get("scope", "full")),
    ).normalized()

    split_files = bool(out.get("split_files", True))
    write_combined = bool(out.get("write_combined_feature_markdown", False))
    readme_merge = str(out.get("readme_feature_merge", "none")).lower().strip()
    if readme_merge not in ALLOWED_README_FEATURE_MERGE:
        readme_merge = "none"
    if readme_merge != "none" and split_files:
        write_combined = True

    inc = feats.get("include")
    if not inc:
        include_set = frozenset(FEATURES)
    else:
        include_set = frozenset(str(x) for x in inc)
    exc = feats.get("exclude") or []
    exclude_set = frozenset(str(x) for x in exc)

    return RunConfig(
        db_type=str(db.get("type", "postgres")),
        uri=str(db.get("uri", "")),
        schema=db.get("schema"),
        database=db.get("database"),
        output_path=Path(out.get("path", "./docs")),
        split_files=split_files,
        write_combined_feature_markdown=write_combined,
        readme_feature_merge=readme_merge,
        include=include_set,
        exclude=exclude_set,
        workers=int(exe.get("workers", 4)),
        limits=dict(lim),
        erd=erd_cfg,
    )
