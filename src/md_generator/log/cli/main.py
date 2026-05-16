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
    p.add_argument("--preset", default=None, help="Parser preset name (e.g. generic, springboot, logback, json)")
    p.add_argument("--line-regex", default=None, help="Custom line regex (named groups: timestamp, level, message, …)")
    p.add_argument("--auto-detect", action="store_true", help="Auto-detect parser preset from log sample")
    p.add_argument(
        "--preset-dir",
        action="append",
        default=None,
        help="Directory with user preset YAML files (repeatable; also MD_LOG_PRESET_DIRS, ~/.mdengine/log/presets)",
    )
    p.add_argument(
        "--async",
        dest="async_job",
        action="store_true",
        help="Enqueue background job (prints job_id; SQLite job store)",
    )
    p.add_argument("--export-jsonl", action="store_true", help="Export embedding-ready JSONL chunks")
    p.add_argument("--export-parquet", action="store_true", help="Export embedding-ready Parquet chunks")
    p.add_argument("--resume", action="store_true", help="Enable incremental checkpoint resume")
    p.add_argument("--frontmatter", action="store_true", help="Emit YAML frontmatter on artifacts")
    sub = p.add_subparsers(dest="command")
    stream_p = sub.add_parser("stream", help="Stream logs from tail/kafka/redis/stdin")
    stream_p.add_argument("--source", choices=["tail", "stdin", "kafka", "redis", "websocket"], default="tail")
    stream_p.add_argument("--config", type=Path, default=None)
    stream_p.add_argument("--input", type=Path, default=None, help="File path for tail source")
    stream_p.add_argument("--output", type=Path, default=None)
    sub.add_parser("presets", help="List available parser presets")
    return p


def _run_stream(ns: argparse.Namespace) -> int:
    import tempfile

    from md_generator.log.core.extractor import extract_to_markdown
    from md_generator.log.core.run_config import load_run_config
    from md_generator.log.streaming.stream_coordinator import iter_stream_lines

    overrides: dict = {"streaming": {"enabled": True, "source": ns.source}}
    if ns.output is not None:
        overrides.setdefault("output", {})["path"] = str(ns.output)
    cfg = load_run_config(ns.config, overrides)
    lines: list[str] = []
    for line in iter_stream_lines(cfg, path=ns.input):
        lines.append(line)
        if len(lines) >= cfg.streaming.batch_size:
            break
    if not lines:
        print("No stream lines received", file=sys.stderr)
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="md-log-stream-"))
    log_file = tmp / "stream.log"
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stream_overrides = {"input": {"paths": [str(log_file)]}, "streaming": {"enabled": False}}
    cfg = load_run_config(ns.config, {**overrides, **stream_overrides})
    extract_to_markdown(cfg.normalized())
    print(str(cfg.output_path().resolve()))
    return 0


def _run_presets() -> int:
    from md_generator.log.config.preset_loader import default_user_preset_dirs, list_preset_names

    for name in list_preset_names():
        print(name)
    for d in default_user_preset_dirs():
        print(f"# user dir: {d}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    if ns.command == "stream":
        return _run_stream(ns)
    if ns.command == "presets":
        return _run_presets()
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
    if getattr(ns, "line_regex", None):
        overrides.setdefault("parser", {})["line_regex"] = ns.line_regex
    if getattr(ns, "auto_detect", False):
        overrides.setdefault("parser", {})["auto_detect"] = True
    if getattr(ns, "preset_dir", None):
        overrides.setdefault("parser", {})["preset_dirs"] = [str(p) for p in ns.preset_dir]
    if ns.export_jsonl:
        overrides.setdefault("embeddings", {})["enabled"] = True
        overrides.setdefault("embeddings", {}).setdefault("exporters", []).append("jsonl")
    if ns.export_parquet:
        overrides.setdefault("embeddings", {})["enabled"] = True
        overrides.setdefault("embeddings", {}).setdefault("exporters", []).append("parquet")
    if getattr(ns, "resume", False):
        overrides.setdefault("incremental", {})["enabled"] = True
    if getattr(ns, "frontmatter", False):
        overrides.setdefault("output", {})["frontmatter"] = True

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
