"""Run a Python script under ``sys.settrace`` and emit CFG-aligned runtime trace JSON.

Output matches :func:`md_generator.codeflow.graph.hotpath.normalize_runtime_trace`
when ``--line-map`` maps source lines to CFG node ids (same strings as ``cfg.json``).
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from typing import Any

from md_generator.codeflow.runtime.python_edge_counter import PythonEdgeCounter


def _path_entry_matches(abs_norm: str, cand: str) -> bool:
    c = cand.replace("\\", "/").strip()
    if not c:
        return False
    return abs_norm == c or abs_norm.endswith(c) or abs_norm.endswith("/" + c.lstrip("./"))


def _cfg_id_for_line(abs_norm: str, lineno: int, mp: dict[str, Any]) -> str | None:
    entries = mp.get("files")
    if not isinstance(entries, list):
        return None
    for ent in entries:
        if not isinstance(ent, dict):
            continue
        suffix = str(ent.get("path_suffix", ""))
        path_key = str(ent.get("path", ""))
        if not (
            _path_entry_matches(abs_norm, suffix)
            or _path_entry_matches(abs_norm, path_key)
        ):
            continue
        lines = ent.get("lines")
        if not isinstance(lines, dict):
            return None
        key = str(lineno)
        if key not in lines:
            return None
        return str(lines[key])
    return None


def run_traced_main(script: Path, argv_tail: list[str], line_map: dict[str, Any]) -> dict[str, Any]:
    script = script.resolve()
    old_argv = sys.argv[:]
    sys.argv = [str(script)] + list(argv_tail)
    counter = PythonEdgeCounter()
    last_cfg: str | None = None

    def tracer(frame, event, arg):  # noqa: ANN001, ARG001
        nonlocal last_cfg
        if event != "line":
            return tracer
        try:
            p = Path(frame.f_code.co_filename).resolve()
            ln = int(frame.f_lineno)
        except (TypeError, ValueError, OSError):
            return tracer
        abs_norm = str(p).replace("\\", "/")
        cid = _cfg_id_for_line(abs_norm, ln, line_map)
        if cid is None:
            return tracer
        if last_cfg is not None and cid != last_cfg:
            counter.record(last_cfg, cid)
        last_cfg = cid
        return tracer

    try:
        sys.settrace(tracer)
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.settrace(None)
        sys.argv = old_argv

    return counter.to_trace_dict()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Trace a Python script and write cfg-runtime-trace JSON (counts: cfg_u->cfg_v).",
    )
    p.add_argument("--output", "-o", type=Path, required=True, help="Destination JSON path")
    p.add_argument(
        "--line-map",
        type=Path,
        required=True,
        help='JSON: {"files":[{"path_suffix":"src/x.py","lines":{"10":"CFG_ID_A","11":"CFG_ID_B"}}]}',
    )
    p.add_argument("script", type=Path, help="Python file to execute as __main__")
    p.add_argument("script_args", nargs=argparse.REMAINDER, default=[], help="Arguments forwarded to script")
    ns = p.parse_args(argv)
    mp = json.loads(Path(ns.line_map).read_text(encoding="utf-8"))
    if not isinstance(mp, dict):
        print("trace_runner: line-map root must be an object", file=sys.stderr)
        return 2
    out = run_traced_main(Path(ns.script), ns.script_args, mp)
    Path(ns.output).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
