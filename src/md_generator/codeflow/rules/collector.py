"""Collect ``BusinessRule`` rows from slice edges, Python AST, optional SQL, and parser-emitted rules."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.models.ir import BusinessRule, FileParseResult
from md_generator.codeflow.parsers.python_parser import _rel_key
from md_generator.codeflow.rules.cpp_rules import extract_cpp_method_rules
from md_generator.codeflow.rules.java_rules import extract_java_method_rules


def _sid_py(file_key: str, class_name: str | None, method_name: str) -> str:
    if class_name:
        return f"{file_key}::{class_name}.{method_name}"
    return f"{file_key}::{method_name}"


def _dedupe_key(r: BusinessRule) -> tuple:
    return (r.source, r.file_path, r.line, r.title, r.detail[:120])


def dedupe_rules(rules: list[BusinessRule]) -> list[BusinessRule]:
    seen: set[tuple] = set()
    out: list[BusinessRule] = []
    for r in rules:
        k = _dedupe_key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _rules_from_slice_edges(sl: FlowSlice, g: nx.DiGraph) -> list[BusinessRule]:
    rules: list[BusinessRule] = []
    seen: set[tuple[str, str, str]] = set()
    for u, v, ed in sl.edges:
        cond = ed.get("condition") or ""
        labs = ed.get("labels") or []
        lab = (labs[-1] if labs else None) or cond
        if not lab:
            continue
        key = (u, v, str(lab))
        if key in seen:
            continue
        seen.add(key)
        fp_u = g.nodes[u].get("file_path", "") if u in g else ""
        ln = int(ed.get("line", 0) or g.nodes[u].get("line", 0) or 0) or 1
        title = f"Branch predicate: `{u}` → `{v}`"
        rules.append(
            BusinessRule(
                source="predicate",
                symbol_id=u,
                file_path=str(fp_u or ""),
                line=ln,
                title=title,
                detail=str(lab),
                confidence="high",
            ),
        )
    return rules


def _decorator_name(d: ast.expr) -> str | None:
    if isinstance(d, ast.Name):
        return d.id
    if isinstance(d, ast.Attribute):
        return d.attr
    if isinstance(d, ast.Call):
        return _decorator_name(d.func)
    return None


_VALIDATION_DECORATORS = frozenset(
    {
        "validator",
        "field_validator",
        "root_validator",
        "model_validator",
        "validate",
    },
)


def _extract_python_method_rules(
    path: Path,
    project_root: Path,
    target_sids: set[str],
) -> list[BusinessRule]:
    rules: list[BusinessRule] = []
    key = _rel_key(path, project_root)
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return rules

    def handle_function(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str | None,
    ) -> None:
        sid = _sid_py(key, class_name, node.name)
        if sid not in target_sids:
            return
        fp = str(path.resolve())
        for dec in node.decorator_list:
            nm = _decorator_name(dec)
            if nm and nm in _VALIDATION_DECORATORS:
                try:
                    snippet = ast.unparse(dec)[:200]
                except Exception:
                    snippet = nm
                rules.append(
                    BusinessRule(
                        source="validation",
                        symbol_id=sid,
                        file_path=fp,
                        line=node.lineno,
                        title=f"Validation decorator `{nm}`",
                        detail=snippet,
                        confidence="medium",
                    ),
                )
        for child in ast.walk(node):
            if isinstance(child, ast.Assert) and child.lineno:
                try:
                    det = ast.unparse(child.test)[:300]
                except Exception:
                    det = "assert …"
                rules.append(
                    BusinessRule(
                        source="validation",
                        symbol_id=sid,
                        file_path=fp,
                        line=child.lineno,
                        title="Assert",
                        detail=det,
                        confidence="low",
                    ),
                )
            if isinstance(child, ast.Raise) and child.lineno:
                try:
                    det = ast.unparse(child.exc)[:300] if child.exc else "raise"
                except Exception:
                    det = "raise …"
                exc_name = ""
                if child.exc and isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                    exc_name = child.exc.func.id
                if exc_name in ("ValueError", "TypeError", "RuntimeError", "KeyError", "AttributeError"):
                    rules.append(
                        BusinessRule(
                            source="validation",
                            symbol_id=sid,
                            file_path=fp,
                            line=child.lineno,
                            title=f"Raise {exc_name}",
                            detail=det,
                            confidence="low",
                        ),
                    )

    for mod_child in tree.body:
        if isinstance(mod_child, ast.ClassDef):
            for body in mod_child.body:
                if isinstance(body, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    handle_function(body, mod_child.name)
        elif isinstance(mod_child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            handle_function(mod_child, None)
    return rules


_CREATE_TRIGGER_RE = re.compile(r"\bCREATE\s+TRIGGER\b", re.IGNORECASE)


def _extract_sql_trigger_lines(path: Path) -> list[BusinessRule]:
    rules: list[BusinessRule] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    fp = str(path.resolve())
    for i, line in enumerate(text.splitlines(), start=1):
        if _CREATE_TRIGGER_RE.search(line):
            title = "SQL trigger"
            stripped = line.strip()[:500]
            rules.append(
                BusinessRule(
                    source="sql_trigger",
                    symbol_id=None,
                    file_path=fp,
                    line=i,
                    title=title,
                    detail=stripped,
                    confidence="medium",
                ),
            )
    return rules


def _slice_nodes_by_file(sl: FlowSlice, g: nx.DiGraph) -> dict[str, set[str]]:
    by_file: dict[str, set[str]] = {}
    for sid in sl.nodes:
        if sid not in g:
            continue
        fp = g.nodes[sid].get("file_path")
        if not fp:
            continue
        by_file.setdefault(str(fp), set()).add(sid)
    return by_file


def _iter_sql_paths(project_root: Path, paths_override: list[Path] | None) -> list[Path]:
    root = project_root.resolve()
    paths: list[Path] = []
    if paths_override:
        bases = {p.resolve().parent if p.is_file() else p.resolve() for p in paths_override}
        for b in bases:
            if b.exists():
                paths.extend(b.rglob("*.sql"))
    else:
        paths.extend(root.rglob("*.sql"))
    # cap for safety
    uniq: dict[str, Path] = {}
    for p in paths:
        try:
            uniq[p.resolve().as_posix()] = p
        except OSError:
            continue
    return list(uniq.values())[:300]


def collect_business_rules(
    _entry_id: str,
    sl: FlowSlice,
    g: nx.DiGraph,
    parse_results: list[FileParseResult],
    cfg: ScanConfig,
    *,
    project_root: Path,
) -> list[BusinessRule]:
    """Gather rules scoped to the flow slice (plus optional workspace SQL when enabled)."""
    if not cfg.business_rules:
        return []

    rules: list[BusinessRule] = []

    slice_nodes = set(sl.nodes)
    for fr in parse_results:
        for r in fr.rules:
            if r.symbol_id is None or r.symbol_id in slice_nodes:
                rules.append(r)

    rules.extend(_rules_from_slice_edges(sl, g))

    by_file = _slice_nodes_by_file(sl, g)
    pr_by_key = {_rel_key(fr.path, project_root): fr for fr in parse_results}

    for rel_fp, sids in by_file.items():
        fr = pr_by_key.get(rel_fp)
        if not fr:
            continue
        if fr.language == "python":
            rules.extend(_extract_python_method_rules(fr.path, project_root, sids))
        elif fr.language == "java":
            rules.extend(extract_java_method_rules(fr.path, project_root, sids))
        elif fr.language == "cpp":
            rules.extend(extract_cpp_method_rules(fr.path, project_root, sids))

    for bp in (b for fr in parse_results for b in fr.branches):
        if bp.caller_id not in sl.nodes:
            continue
        fp = g.nodes[bp.caller_id].get("file_path", "") if bp.caller_id in g else ""
        lab = bp.label or bp.kind
        rules.append(
            BusinessRule(
                source="branch",
                symbol_id=bp.caller_id,
                file_path=str(fp or ""),
                line=bp.line,
                title=f"Branch ({bp.kind})",
                detail=str(lab),
                confidence="medium",
            ),
        )

    if cfg.business_rules_sql:
        for sql_path in _iter_sql_paths(project_root, cfg.paths_override):
            rules.extend(_extract_sql_trigger_lines(sql_path))

    return dedupe_rules(rules)
