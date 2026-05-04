from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from md_generator.codeflow.core.extractor import run_scan
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.ingestion.git_loader import (
    GitLoaderError,
    clean_all_cache,
    clone_or_update_repo,
    is_git_remote,
)
from md_generator.codeflow.ingestion.loader import LoadedWorkspace, load_workspace, source_file_extensions


def _parse_formats(s: str | None) -> tuple[str, ...]:
    if s is None or not str(s).strip():
        return ("md", "mermaid", "json")
    parts = tuple(x.strip().lower() for x in str(s).split(",") if x.strip())
    return parts if parts else ("md", "mermaid", "json")


def _parse_entry(s: str | None) -> list[str] | None:
    if not s or not str(s).strip():
        return None
    return [x.strip() for x in str(s).split(",") if x.strip()]


def _parse_csv_identifiers(s: str | None) -> tuple[str, ...]:
    if not s or not str(s).strip():
        return ()
    return tuple(x.strip() for x in str(s).split(",") if x.strip())


def _normalize_include(raw: str | None) -> str | None:
    if not raw:
        return None
    mapping = {
        "api": "api_rest",
        "rest": "api_rest",
        "portlet": "portlet",
        "liferay": "portlet",
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
    scan = sub.add_parser("scan", help="Scan a folder, file, .zip archive, or Git remote URL")
    scan.add_argument(
        "path",
        type=str,
        nargs="?",
        default=None,
        help="Local directory, source file, .zip, or https/git remote URL (omit when using --clean-git-cache only)",
    )
    scan.add_argument("--output", "-o", type=Path, default=None, help="Output directory")
    scan.add_argument("--entry", default=None, help="Comma-separated symbol ids (Class.method style)")
    scan.add_argument(
        "--lang",
        default="mixed",
        help=(
            "mixed | python | java | javascript | typescript | tsx | cpp | go | php | "
            "comma-separated (e.g. python,javascript). Aliases: js→javascript, ts→typescript."
        ),
    )
    scan.add_argument("--formats", "--output-formats", dest="formats", default=None, help="Comma-separated: md,html,mermaid,json")
    scan.add_argument("--depth", type=int, default=5)
    scan.add_argument("--include", default=None, help="Filter entry kinds: api,event,main,...")
    scan.add_argument("--exclude", default=None, help="Reserved for path/symbol exclusions")
    scan.add_argument("--async", dest="async_flag", action="store_true", default=True)
    scan.add_argument("--no-async", dest="async_flag", action="store_false")
    scan.add_argument("--jobs", action="store_true", default=False, help="No-op in CLI (reserved for API)")
    scan.add_argument("--runtime", action="store_true", default=False, help="Reserved: runtime tracing")
    scan.add_argument(
        "--business-rules",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Emit business_rules.md, entry section, and (unless disabled) entry.combined.md (default: on)",
    )
    scan.add_argument(
        "--business-rules-sql",
        action="store_true",
        default=False,
        help="Scan workspace *.sql for CREATE TRIGGER lines",
    )
    scan.add_argument(
        "--business-rules-combined",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write entry.combined.md (entry.md + business_rules.md) (default: on)",
    )
    scan.add_argument(
        "--entry-fallback",
        choices=["none", "roots", "first_n"],
        default="roots",
        help="When no detected entries: none | in-degree-0 roots | first N symbols (default: roots)",
    )
    scan.add_argument(
        "--entry-fallback-max",
        type=int,
        default=20,
        help="Max symbols when using roots or first_n fallback (default: 20)",
    )
    scan.add_argument(
        "--emit-entry-per-method",
        action="store_true",
        default=False,
        help="Emit one output slug per method/entry symbol (use --emit-entry-max to cap)",
    )
    scan.add_argument(
        "--emit-entry-max",
        type=int,
        default=None,
        help="Cap for --emit-entry-per-method (default: 10000 when flag set and unset)",
    )
    scan.add_argument(
        "--emit-entry-filter",
        default=None,
        help="Regex filter on symbol_id when using --emit-entry-per-method",
    )
    scan.add_argument(
        "--entries-file",
        type=Path,
        default=None,
        help="File with one symbol_id per line (# comments allowed); resolved paths",
    )
    scan.add_argument(
        "--no-scan-summary",
        action="store_true",
        default=False,
        help="Skip writing scan-summary.md at output root",
    )
    scan.add_argument(
        "--liferay-portlet-bases",
        default=None,
        help="Extra Liferay portlet superclass simple names (comma-separated); merged with built-in defaults",
    )
    scan.add_argument(
        "--codeflow-config",
        type=Path,
        default=None,
        help="Path to codeflow.yaml (default: <project_root>/codeflow.yaml if present)",
    )
    scan.add_argument(
        "--emit-flow-tree-json",
        action="store_true",
        default=False,
        help="Write flow-tree.json (static DFS tree from the flow slice) beside each entry output",
    )
    scan.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG logging for md_generator.codeflow",
    )
    scan.add_argument(
        "--emit-graph-schema",
        action="store_true",
        default=False,
        help="With json format, also write graph-schema.json (stable Node/Edge view with File/Class hierarchy)",
    )
    scan.add_argument(
        "--intelligence-list-cap",
        type=int,
        default=80,
        help="Max items for Called by / Impact lists in Markdown (default: 80)",
    )
    scan.add_argument(
        "--emit-cfg",
        action="store_true",
        default=False,
        help="Build IR-based CFG per entry (cfg.json, cfg.mmd; append CFG Mermaid to flow.md when md is enabled)",
    )
    scan.add_argument(
        "--cfg-max-nodes",
        type=int,
        default=500,
        help="Safety cap on CFG nodes when using --emit-cfg (default: 500)",
    )
    scan.add_argument(
        "--cfg-inline-calls",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When using --emit-cfg, inline callee CFGs at CALL nodes (default: off)",
    )
    scan.add_argument(
        "--cfg-call-depth",
        type=int,
        default=3,
        help="Max CALL inlining depth when --cfg-inline-calls (default: 3)",
    )
    scan.add_argument(
        "--cfg-max-paths",
        type=int,
        default=100,
        help="Max enumerated START→END paths when using --emit-cfg (default: 100)",
    )
    scan.add_argument(
        "--cfg-path-max-depth",
        type=int,
        default=1000,
        help="Max DFS depth for path enumeration (default: 1000)",
    )
    scan.add_argument(
        "--cfg-loop-visits",
        type=int,
        default=2,
        help="Max LOOP_HDR revisits per path before forcing exit edges (default: 2)",
    )
    scan.add_argument(
        "--graph-include-structural",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Merge parser structural edges (IMPORTS / INHERITS / …; Java) into the graph (default: off)",
    )
    scan.add_argument(
        "--intelligence-transitive-callers",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="List transitive callers in Called By sections (default: direct only)",
    )
    scan.add_argument(
        "--emit-system-graph-stats",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Append graph inventory (counts, top out-degree) to system_overview.md",
    )
    scan.add_argument(
        "--emit-graph-sqlite",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write graph.db (SQLite nodes/edges) alongside graph-full.json",
    )
    scan.add_argument(
        "--emit-graph-communities",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When json format is on, write graph-communities.json (greedy modularity on file imports)",
    )
    scan.add_argument(
        "--emit-llm-entry-sidecar",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write entry.llm.md beside each entry.md (pointers for LLM workflows)",
    )
    scan.add_argument(
        "--git-branch",
        "--branch",
        dest="git_branch",
        default=None,
        help="After clone/update, check out this branch (Git remote input only)",
    )
    scan.add_argument(
        "--git-commit",
        "--commit",
        dest="git_commit",
        default=None,
        help="After branch (or default), check out this commit SHA (Git remote input only)",
    )
    scan.add_argument(
        "--git-auth-token",
        default=None,
        help="HTTPS token (injected per host; never printed). Prefer env-specific URLs in CI.",
    )
    scan.add_argument(
        "--git-ssh-key",
        type=Path,
        default=None,
        help="Path to SSH private key for git@… remotes (sets GIT_SSH_COMMAND for clone/pull)",
    )
    scan.add_argument(
        "--no-git-cache",
        action="store_true",
        default=False,
        help="Delete cached clone for this URL and re-clone fresh",
    )
    scan.add_argument(
        "--clean-git-cache",
        action="store_true",
        default=False,
        help="Remove all cached Git clones under the codeflow cache dir, then exit (no scan)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ns = build_parser().parse_args(argv)
    if ns.cmd != "scan":
        return 2

    if ns.clean_git_cache:
        clean_all_cache()
        print("Removed codeflow Git clone cache.", file=sys.stderr)
        return 0

    if not ns.path or not str(ns.path).strip():
        print("codeflow scan: error: path is required (unless using --clean-git-cache)", file=sys.stderr)
        return 2

    raw = str(ns.path).strip()
    if ns.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
        logging.getLogger("md_generator.codeflow").setLevel(logging.DEBUG)

    paths_override: list[Path] | None = None
    if is_git_remote(raw):
        try:
            root = clone_or_update_repo(
                raw,
                branch=ns.git_branch,
                commit=ns.git_commit,
                no_cache=bool(ns.no_git_cache),
                auth_token=ns.git_auth_token,
                ssh_key_path=ns.git_ssh_key,
            )
        except GitLoaderError as e:
            print(str(e), file=sys.stderr)
            return 1
        ws = LoadedWorkspace(root=root, cleanup_dir=None)
    else:
        src = Path(raw).expanduser().resolve()
        ws = load_workspace(path=src)
        root = ws.root
        if src.is_file() and src.suffix.lower() in source_file_extensions():
            paths_override = [src]

    try:
        out = ns.output
        if out is None:
            out = Path.cwd() / "codeflow-out"
        entries_file = Path(ns.entries_file).expanduser().resolve() if ns.entries_file else None
        codeflow_cfg = Path(ns.codeflow_config).expanduser().resolve() if ns.codeflow_config else None
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
            business_rules=bool(ns.business_rules),
            business_rules_sql=bool(ns.business_rules_sql),
            business_rules_combined=bool(ns.business_rules_combined),
            entry_fallback=ns.entry_fallback,
            entry_fallback_max=int(ns.entry_fallback_max),
            emit_entry_per_method=bool(ns.emit_entry_per_method),
            emit_entry_max=ns.emit_entry_max,
            emit_entry_filter=ns.emit_entry_filter,
            entries_file=entries_file,
            write_scan_summary=not bool(ns.no_scan_summary),
            liferay_portlet_base_classes=_parse_csv_identifiers(ns.liferay_portlet_bases),
            codeflow_config_path=codeflow_cfg,
            emit_flow_tree_json=bool(ns.emit_flow_tree_json),
            verbose=bool(ns.verbose),
            emit_graph_schema=bool(ns.emit_graph_schema),
            intelligence_list_cap=int(ns.intelligence_list_cap),
            emit_cfg=bool(ns.emit_cfg),
            cfg_max_nodes=int(ns.cfg_max_nodes),
            cfg_inline_calls=bool(ns.cfg_inline_calls),
            cfg_call_depth=int(ns.cfg_call_depth),
            cfg_max_paths=int(ns.cfg_max_paths),
            cfg_path_max_depth=int(ns.cfg_path_max_depth),
            cfg_loop_visits=int(ns.cfg_loop_visits),
            graph_include_structural=bool(ns.graph_include_structural),
            intelligence_transitive_callers=bool(ns.intelligence_transitive_callers),
            emit_system_graph_stats=bool(ns.emit_system_graph_stats),
            emit_graph_sqlite=bool(ns.emit_graph_sqlite),
            emit_graph_communities=bool(ns.emit_graph_communities),
            emit_llm_entry_sidecar=bool(ns.emit_llm_entry_sidecar),
        )
        run_scan(cfg, workspace=ws)
        print(str(cfg.output_path.resolve()))
        return 0
    finally:
        ws.close()  # no-op for Git cache / plain dirs; removes zip temp dirs


if __name__ == "__main__":
    raise SystemExit(main())
