"""PHP parsing via nikic/php-parser (JSON bridge in ``tools/codeflow_php_dump`` or ``codeflow-to-md/examples/codeflow_php_dump``)."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from md_generator.codeflow.models.ir import BranchPoint, BusinessRule, CallSite, CallResolution, FileParseResult
from md_generator.codeflow.utils.tools_root import find_tools_dir

logger = logging.getLogger(__name__)


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


class PhpParser:
    language = "php"

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        fr = FileParseResult(path=path.resolve(), language=self.language)
        tool = find_tools_dir("codeflow_php_dump")
        if not tool or not (tool / "dump.php").is_file():
            logger.debug("codeflow_php_dump missing; skip %s", path)
            return fr
        php = shutil.which("php")
        if php is None:
            logger.debug("php not on PATH; skip %s", path)
            return fr
        rel = _rel_key(path, project_root)
        script = tool / "dump.php"
        try:
            proc = subprocess.run(
                [php, str(script), str(path.resolve()), rel],
                cwd=str(tool),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as e:
            logger.debug("php dump failed for %s: %s", path, e)
            return fr
        if proc.returncode != 0:
            logger.debug("php dump stderr: %s", (proc.stderr or "")[:500])
            return fr
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return fr
        if isinstance(data, dict) and data.get("error"):
            return fr
        fp = str(path.resolve())
        for fn in data.get("funcs", []) or []:
            fid = fn.get("id")
            if fid and fid not in fr.symbol_ids:
                fr.symbol_ids.append(fid)
            for c in fn.get("calls", []) or []:
                callee = str(c.get("callee") or "")
                caller = str(c.get("caller") or fid or "")
                line = int(c.get("line") or 0)
                cond_raw = c.get("condition")
                cond = str(cond_raw).strip() if cond_raw else None
                res: CallResolution = "static" if callee.isidentifier() else "dynamic"
                fr.calls.append(
                    CallSite(
                        caller_id=caller,
                        callee_hint=callee or "unknown::call",
                        resolution=res,
                        is_async=False,
                        line=line,
                        condition_label=cond,
                    ),
                )
            for r in fn.get("rules", []) or []:
                if not isinstance(r, dict):
                    continue
                sid = str(r.get("symbolId") or r.get("symbol_id") or "")
                if not sid:
                    continue
                fr.rules.append(
                    BusinessRule(
                        source="validation",
                        symbol_id=sid,
                        file_path=fp,
                        line=int(r.get("line") or 0) or 1,
                        title=str(r.get("title") or "Rule"),
                        detail=str(r.get("detail") or ""),
                        confidence="medium",
                    ),
                )
            for b in fn.get("branches", []) or []:
                if not isinstance(b, dict):
                    continue
                cid = str(b.get("callerId") or b.get("caller_id") or "")
                if not cid:
                    continue
                fr.branches.append(
                    BranchPoint(
                        caller_id=cid,
                        kind=str(b.get("kind") or "if"),
                        label=str(b.get("label") or "") or None,
                        line=int(b.get("line") or 0) or 1,
                    ),
                )
        return fr
