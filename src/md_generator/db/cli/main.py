from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.db.core.extractor import extract_to_markdown
from md_generator.db.core.job_manager import JobManager
from md_generator.db.core.models import FEATURES
from md_generator.db.core.run_config import ErdConfig, RunConfig, load_run_config


def _parse_csv(s: str | None) -> frozenset[str] | None:
    if s is None or not s.strip():
        return None
    return frozenset(x.strip() for x in s.split(",") if x.strip())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export database metadata to Markdown.")
    p.add_argument("--config", type=Path, default=None, help="Path to YAML config")
    p.add_argument("--type", dest="db_type", default=None, help="postgres|mysql|oracle|mongo")
    p.add_argument("--uri", default=None)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--include", default=None, help="Comma-separated feature list")
    p.add_argument("--exclude", default=None)
    p.add_argument("--schema", default=None)
    p.add_argument("--database", default=None, help="Mongo database name")
    p.add_argument("--split-files", choices=("true", "false"), default=None)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument(
        "--async",
        dest="async_job",
        action="store_true",
        help="Enqueue background job (prints job_id; uses SQLite job store)",
    )
    p.add_argument("--erd-max-tables", type=int, default=None, help="ERD: max tables (default from config, usually 100)")
    p.add_argument(
        "--erd-scope",
        choices=("full", "per_schema", "per_table"),
        default=None,
        help="ERD: full | per_schema | per_table",
    )
    p.add_argument(
        "--write-combined-feature-markdown",
        choices=("true", "false"),
        default=None,
        help="When split_files, also write root tables.md, views.md, … bundles",
    )
    p.add_argument(
        "--readme-feature-merge",
        choices=("none", "inline", "toc"),
        default=None,
        help="Append combined bundle docs to README: none | inline | toc",
    )
    return p


def _apply_cli_overrides(cfg: RunConfig, ns: argparse.Namespace) -> RunConfig:
    from dataclasses import replace

    kw: dict = {}
    if ns.db_type:
        kw["db_type"] = ns.db_type
    if ns.uri:
        kw["uri"] = ns.uri
    if ns.output:
        kw["output_path"] = ns.output
    if ns.schema is not None:
        kw["schema"] = ns.schema
    if ns.database is not None:
        kw["database"] = ns.database
    if ns.workers is not None:
        kw["workers"] = ns.workers
    inc = _parse_csv(ns.include)
    if inc is not None:
        bad = inc - FEATURES
        if bad:
            raise SystemExit(f"Unknown features in --include: {sorted(bad)}")
        kw["include"] = inc
    exc = _parse_csv(ns.exclude)
    if exc is not None:
        bad = exc - FEATURES
        if bad:
            raise SystemExit(f"Unknown features in --exclude: {sorted(bad)}")
        kw["exclude"] = exc
    if ns.split_files is not None:
        kw["split_files"] = ns.split_files == "true"
    if getattr(ns, "write_combined_feature_markdown", None) is not None:
        kw["write_combined_feature_markdown"] = ns.write_combined_feature_markdown == "true"
    if getattr(ns, "readme_feature_merge", None) is not None:
        kw["readme_feature_merge"] = ns.readme_feature_merge
    if ns.erd_max_tables is not None or ns.erd_scope is not None:
        ec = cfg.erd
        kw["erd"] = ErdConfig(
            max_tables=ns.erd_max_tables if ns.erd_max_tables is not None else ec.max_tables,
            scope=ns.erd_scope if ns.erd_scope is not None else ec.scope,
        ).normalized()
    return replace(cfg, **kw) if kw else cfg


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    cfg_path = ns.config
    if cfg_path is not None and not cfg_path.is_file():
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        return 2
    overrides: dict = {}
    if ns.db_type:
        overrides.setdefault("database", {})["type"] = ns.db_type
    if ns.uri:
        overrides.setdefault("database", {})["uri"] = ns.uri
    if ns.schema is not None:
        overrides.setdefault("database", {})["schema"] = ns.schema
    if ns.database is not None:
        overrides.setdefault("database", {})["database"] = ns.database
    if ns.output:
        overrides.setdefault("output", {})["path"] = str(ns.output)
    if ns.split_files is not None:
        overrides.setdefault("output", {})["split_files"] = ns.split_files == "true"
    if getattr(ns, "write_combined_feature_markdown", None) is not None:
        overrides.setdefault("output", {})["write_combined_feature_markdown"] = (
            ns.write_combined_feature_markdown == "true"
        )
    if getattr(ns, "readme_feature_merge", None) is not None:
        overrides.setdefault("output", {})["readme_feature_merge"] = ns.readme_feature_merge
    if ns.workers is not None:
        overrides.setdefault("execution", {})["workers"] = ns.workers
    if getattr(ns, "erd_max_tables", None) is not None:
        overrides.setdefault("erd", {})["max_tables"] = ns.erd_max_tables
    if getattr(ns, "erd_scope", None) is not None:
        overrides.setdefault("erd", {})["scope"] = ns.erd_scope
    inc = _parse_csv(ns.include)
    if inc is not None:
        overrides.setdefault("features", {})["include"] = list(sorted(inc))
    exc = _parse_csv(ns.exclude)
    if exc is not None:
        overrides.setdefault("features", {})["exclude"] = list(sorted(exc))

    cfg = load_run_config(cfg_path if cfg_path is not None else None, overrides if overrides else None)
    cfg = _apply_cli_overrides(cfg, ns)

    if ns.async_job:
        jm = JobManager()
        try:
            rec = jm.create_job(cfg)
            jm.run_job_thread(rec.job_id)
            print(rec.job_id)
        finally:
            jm.close()
        return 0

    try:
        extract_to_markdown(cfg)
    except Exception as e:
        print(f"db-to-md failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
