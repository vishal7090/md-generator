from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.codeflow.core.extractor import run_scan
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.ingestion.loader import load_workspace


def _parse_formats(s: str | None) -> tuple[str, ...]:
    if s is None or not str(s).strip():
        return ("md", "mermaid", "json")
    parts = tuple(x.strip().lower() for x in str(s).split(",") if x.strip())
    return parts if parts else ("md", "mermaid", "json")


def _parse_entry(s: str | None) -> list[str] | None:
    if not s or not str(s).strip():
        return None
    return [x.strip() for x in str(s).split(",") if x.strip()]


def _normalize_include(raw: str | None) -> str | None:
    if not raw:
        return None
    mapping = {
        "api": "api_rest",
        "rest": "api_rest",
        "event": "kafka",
        "kafka": "kafka",
        "main": "main",
        "cli": "cli",
        "scheduler": "scheduler",
        "queue": "queue",
    }
    parts = []
    for x in raw.split(","):
        x = x.strip().lower()
        parts.append(mapping.get(x, x))
    return ",".join(parts)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Analyze source code execution flows → Markdown/Mermaid/graph.")
    sub = p.add_subparsers(dest="cmd", required=True)
    scan = sub.add_parser("scan", help="Scan a folder, file, or zip archive")
    scan.add_argument("path", type=Path, help="Directory, source file, or .zip archive")
    scan.add_argument("--output", "-o", type=Path, default=None, help="Output directory")
    scan.add_argument("--entry", default=None, help="Comma-separated symbol ids (Class.method style)")
    scan.add_argument("--lang", default="mixed", choices=("mixed", "python", "java"))
    scan.add_argument("--formats", "--output-formats", dest="formats", default=None, help="Comma-separated: md,html,mermaid,json")
    scan.add_argument("--depth", type=int, default=5)
    scan.add_argument("--include", default=None, help="Filter entry kinds: api,event,main,...")
    scan.add_argument("--exclude", default=None, help="Reserved for path/symbol exclusions")
    scan.add_argument("--async", dest="async_flag", action="store_true", default=True)
    scan.add_argument("--no-async", dest="async_flag", action="store_false")
    scan.add_argument("--jobs", action="store_true", default=False, help="No-op in CLI (reserved for API)")
    scan.add_argument("--runtime", action="store_true", default=False, help="Reserved: runtime tracing")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ns = build_parser().parse_args(argv)
    if ns.cmd != "scan":
        return 2

    src = Path(ns.path).expanduser().resolve()
    ws = load_workspace(path=src)
    try:
        root = ws.root
        paths_override: list[Path] | None = None
        if src.is_file() and src.suffix.lower() in (".py", ".java"):
            paths_override = [src]

        out = ns.output
        if out is None:
            out = Path.cwd() / "codeflow-out"
        cfg = ScanConfig(
            project_root=root,
            paths_override=paths_override,
            output_path=out.resolve(),
            formats=_parse_formats(ns.formats),
            depth=int(ns.depth),
            languages=str(ns.lang),
            entry=_parse_entry(ns.entry),
            include=_normalize_include(ns.include),
            exclude=ns.exclude,
            include_internal=True,
            async_mode=bool(ns.async_flag),
            jobs=bool(ns.jobs),
            runtime=bool(ns.runtime),
        )
        run_scan(cfg, workspace=ws)
        print(str(cfg.output_path.resolve()))
        return 0
    finally:
        ws.close()


if __name__ == "__main__":
    raise SystemExit(main())
