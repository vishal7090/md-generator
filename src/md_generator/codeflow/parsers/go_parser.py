"""Go parsing via ``go/parser`` (JSON bridge in ``tools/codeflow_go_dump``)."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from md_generator.codeflow.models.ir import CallSite, CallResolution, FileParseResult
from md_generator.codeflow.utils.tools_root import find_tools_dir

logger = logging.getLogger(__name__)


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


class GoParser:
    language = "go"

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        fr = FileParseResult(path=path.resolve(), language=self.language)
        tool = find_tools_dir("codeflow_go_dump")
        if not tool or not (tool / "main.go").is_file():
            logger.debug("codeflow_go_dump tool missing; skip %s", path)
            return fr
        if shutil.which("go") is None:
            logger.debug("go not on PATH; skip %s", path)
            return fr
        rel = _rel_key(path, project_root)
        try:
            proc = subprocess.run(
                ["go", "run", ".", str(path.resolve()), rel],
                cwd=str(tool),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as e:
            logger.debug("go dump failed for %s: %s", path, e)
            return fr
        if proc.returncode != 0:
            logger.debug("go dump stderr: %s", proc.stderr[:500] if proc.stderr else "")
            return fr
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return fr
        if isinstance(data, dict) and data.get("error"):
            return fr
        for fn in data.get("funcs", []) or []:
            fid = fn.get("id")
            if fid and fid not in fr.symbol_ids:
                fr.symbol_ids.append(fid)
            raw_calls = fn.get("calls") or []
            if not isinstance(raw_calls, list):
                raw_calls = []
            for c in raw_calls:
                callee = str(c.get("Callee") or c.get("callee") or "")
                caller = str(c.get("Caller") or c.get("caller") or fid or "")
                line = int(c.get("Line") or c.get("line") or 0)
                res: CallResolution = "dynamic"
                if "." not in callee and callee.isidentifier():
                    res = "static"
                fr.calls.append(
                    CallSite(
                        caller_id=caller,
                        callee_hint=callee or "unknown::call",
                        resolution=res,
                        is_async=False,
                        line=line,
                        condition_label=None,
                    )
                )
        return fr
