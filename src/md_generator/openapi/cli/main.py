from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.openapi.core.extractor import extract_to_markdown
from md_generator.openapi.core.run_config import ApiRunConfig, load_api_run_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export OpenAPI specifications to Markdown.")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="Generate Markdown, HTML, and Mermaid outputs")
    src = g.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", type=Path, default=None, help="Path to openapi.yaml/json")
    src.add_argument("--folder", type=Path, default=None, help="Directory containing OpenAPI spec")
    src.add_argument("--zip", type=Path, default=None, help="ZIP archive containing OpenAPI spec")
    src.add_argument("--url", default=None, help="URL of OpenAPI document")
    g.add_argument("--config", type=Path, default=None, help="YAML config (input/output/openapi)")
    g.add_argument("--output", type=Path, default=None, help="Output directory")
    g.add_argument(
        "--formats",
        default=None,
        help="Comma-separated: md,html,mermaid (default from config or md,mermaid)",
    )
    g.add_argument(
        "--preferred-media-type",
        default=None,
        help="Preferred request/response media type (default application/json)",
    )
    return p


def _parse_formats(s: str | None) -> tuple[str, ...] | None:
    if s is None or not str(s).strip():
        return None
    parts = tuple(x.strip().lower() for x in str(s).split(",") if x.strip())
    return parts or None


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ns = build_parser().parse_args(argv)
    if ns.cmd != "generate":
        return 2
    cfg = load_api_run_config(ns.config, None)
    kw: dict = {}
    if ns.file is not None:
        kw["file"] = ns.file
    if ns.folder is not None:
        kw["folder"] = ns.folder
    if ns.zip is not None:
        kw["zip"] = ns.zip
    if ns.url is not None:
        kw["url"] = str(ns.url)
    if ns.output is not None:
        kw["output_path"] = ns.output
    fmts = _parse_formats(ns.formats)
    if fmts is not None:
        kw["formats"] = fmts
    if ns.preferred_media_type is not None:
        kw["preferred_media_type"] = ns.preferred_media_type
    if kw:
        from dataclasses import replace

        cfg = replace(cfg, **kw)
    cfg = cfg.normalized()
    sources = sum(1 for x in (cfg.file, cfg.folder, cfg.zip, cfg.url) if x is not None)
    if sources != 1:
        print("Specify exactly one of: --file, --folder, --zip, --url", file=sys.stderr)
        return 2
    extract_to_markdown(cfg)
    print(str(cfg.output_path.resolve()))
    return 0
