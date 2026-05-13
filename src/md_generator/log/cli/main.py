from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.log.core.extractor import extract_to_markdown
from md_generator.log.core.job_manager import LogJobManager
from md_generator.log.core.run_config import load_run_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Normalize logs to AI-oriented Markdown.")
    p.add_argument("--config", type=Path, default=None, help="YAML config path")
    p.add_argument("--input", type=Path, action="append", default=None, help="Log file or directory (repeatable)")
    p.add_argument("--output", type=Path, default=None, help="Output directory")
    p.add_argument("--preset", default=None, help="Parser preset name (e.g. generic, springboot)")
    p.add_argument(
        "--async",
        dest="async_job",
        action="store_true",
        help="Enqueue background job (prints job_id; SQLite job store)",
    )
    p.add_argument("--export-jsonl", action="store_true", help="Export embedding-ready JSONL chunks")
    p.add_argument("--export-parquet", action="store_true", help="Export embedding-ready Parquet chunks")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    cfg_path = ns.config
    if cfg_path is not None and not cfg_path.is_file():
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        return 2

    overrides: dict = {}
    if ns.input:
        overrides.setdefault("input", {})["paths"] = [str(p) for p in ns.input]
    if ns.output is not None:
        overrides.setdefault("output", {})["path"] = str(ns.output)
    if ns.preset is not None:
        overrides.setdefault("parser", {})["preset"] = ns.preset
    if ns.export_jsonl:
        overrides.setdefault("embeddings", {})["enabled"] = True
        overrides.setdefault("embeddings", {}).setdefault("exporters", []).append("jsonl")
    if ns.export_parquet:
        overrides.setdefault("embeddings", {})["enabled"] = True
        overrides.setdefault("embeddings", {}).setdefault("exporters", []).append("parquet")

    cfg = load_run_config(cfg_path if cfg_path is not None else None, overrides if overrides else None)
    cfg = cfg.normalized()

    if not cfg.resolved_input_paths():
        print("No input: set input.paths in config or pass --input", file=sys.stderr)
        return 2

    if ns.async_job:
        jm = LogJobManager()
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
        print(f"log-to-md failed: {e}", file=sys.stderr)
        return 1
    print(str(cfg.output_path().resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
