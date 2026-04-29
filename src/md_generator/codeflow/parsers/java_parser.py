from __future__ import annotations

from pathlib import Path

import javalang.tree

from md_generator.codeflow.models.ir import (
    BranchPoint,
    CallSite,
    CallResolution,
    EntryKind,
    EntryRecord,
    FileParseResult,
)


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sid(key: str, cls: str, method: str) -> str:
    return f"{key}::{cls}.{method}"


def _is_jtree(x: object) -> bool:
    return x is not None and getattr(type(x), "__module__", "") == javalang.tree.__name__


def _snippet_from_source(source: str, node: object, max_len: int = 120) -> str:
    pos = getattr(node, "position", None)
    line = int(getattr(pos, "line", 0) or 0) if pos else 0
    if line > 0 and source:
        lines = source.splitlines()
        if 0 < line <= len(lines):
            s = lines[line - 1].strip()
            if len(s) > max_len:
                return s[: max_len] + "…"
            return s
    return "…"


def _switch_case_label(case_node: object) -> str:
    parts = getattr(case_node, "case", None) or []
    if not parts:
        return "default"
    bits: list[str] = []
    for e in parts:
        if hasattr(e, "value"):
            bits.append(str(getattr(e, "value", e)))
        else:
            bits.append(str(getattr(e, "name", e))[:40])
    return "case " + ", ".join(bits)


def _format_invocation(expr: object) -> str:
    qual = getattr(expr, "qualifier", None) or ""
    member = getattr(expr, "member", "") or ""
    if qual and not isinstance(qual, str):
        qual = ""
    if qual:
        return f"{qual}.{member}"
    return member or "unknown"


def _resolution_for_invocation(expr: object) -> CallResolution:
    qual = getattr(expr, "qualifier", None) or ""
    return "static" if qual else "dynamic"


def _walk_expr(
    expr: object,
    source: str,
    caller: str,
    fr: FileParseResult,
    cond_stack: list[str],
) -> None:
    if expr is None:
        return
    if isinstance(expr, javalang.tree.MethodInvocation):
        callee = JavaParser._format_invocation_static(expr)
        pos = getattr(expr, "position", None)
        line = int(getattr(pos, "line", 0) or 0) if pos else 0
        cond = cond_stack[-1] if cond_stack else None
        fr.calls.append(
            CallSite(
                caller_id=caller,
                callee_hint=callee,
                resolution=JavaParser._resolution_static(expr),
                is_async=False,
                line=line,
                condition_label=cond,
            ),
        )
        qual = getattr(expr, "qualifier", None)
        if qual is not None and not isinstance(qual, str):
            _walk_expr(qual, source, caller, fr, cond_stack)
        for a in getattr(expr, "arguments", None) or []:
            _walk_expr(a, source, caller, fr, cond_stack)
        for sel in getattr(expr, "selectors", None) or []:
            _walk_expr(sel, source, caller, fr, cond_stack)
        return
    if isinstance(expr, javalang.tree.TernaryExpression):
        lab = _snippet_from_source(source, expr.condition)
        _walk_expr(expr.if_true, source, caller, fr, cond_stack + [lab])
        _walk_expr(expr.if_false, source, caller, fr, cond_stack + ["else"])
        return
    if isinstance(expr, javalang.tree.LambdaExpression):
        body = getattr(expr, "body", None)
        if isinstance(body, javalang.tree.BlockStatement):
            _walk_block(body.statements or [], source, caller, fr, cond_stack)
        else:
            _walk_expr(body, source, caller, fr, cond_stack)
        return
    if isinstance(expr, javalang.tree.ClassCreator):
        for a in getattr(expr, "arguments", None) or []:
            _walk_expr(a, source, caller, fr, cond_stack)
        return
    if isinstance(expr, javalang.tree.ArrayInitializer):
        for el in getattr(expr, "values", None) or []:
            _walk_expr(el, source, caller, fr, cond_stack)
        return
    for name in getattr(expr, "attrs", ()) or ():
        if name in ("position", "label", "attrs", "documentation"):
            continue
        val = getattr(expr, name, None)
        if val is None:
            continue
        if isinstance(val, list):
            for x in val:
                if _is_jtree(x):
                    _walk_expr(x, source, caller, fr, cond_stack)
        elif _is_jtree(val):
            _walk_expr(val, source, caller, fr, cond_stack)


def _walk_block(
    statements: list,
    source: str,
    caller: str,
    fr: FileParseResult,
    cond_stack: list[str],
) -> None:
    for stmt in statements or []:
        _walk_stmt(stmt, source, caller, fr, cond_stack)


def _walk_stmt(
    stmt: object,
    source: str,
    caller: str,
    fr: FileParseResult,
    cond_stack: list[str],
) -> None:
    if stmt is None:
        return
    if isinstance(stmt, javalang.tree.BlockStatement):
        _walk_block(stmt.statements or [], source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.IfStatement):
        lab = _snippet_from_source(source, stmt.condition)
        pos = getattr(stmt, "position", None)
        ln = int(getattr(pos, "line", 0) or 0) if pos else 0
        fr.branches.append(BranchPoint(caller_id=caller, kind="if", label=lab, line=ln or 1))
        _walk_stmt(stmt.then_statement, source, caller, fr, cond_stack + [lab])
        if stmt.else_statement is not None:
            _walk_stmt(stmt.else_statement, source, caller, fr, cond_stack + ["else"])
        return
    if isinstance(stmt, javalang.tree.SwitchStatement):
        pos = getattr(stmt, "position", None)
        ln = int(getattr(pos, "line", 0) or 0) if pos else 0
        for case in stmt.cases or []:
            clab = _switch_case_label(case)
            fr.branches.append(BranchPoint(caller_id=caller, kind="switch", label=clab, line=ln or 1))
            _walk_block(case.statements or [], source, caller, fr, cond_stack + [clab])
        return
    if isinstance(stmt, javalang.tree.ForStatement):
        _walk_stmt(stmt.body, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.WhileStatement):
        _walk_stmt(stmt.body, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.DoStatement):
        _walk_stmt(stmt.body, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.TryStatement):
        _walk_stmt(stmt.block, source, caller, fr, cond_stack)
        for c in stmt.catches or []:
            _walk_stmt(c.block, source, caller, fr, cond_stack)
        if stmt.finally_block is not None:
            _walk_stmt(stmt.finally_block, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.SynchronizedStatement):
        _walk_stmt(stmt.block, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.ReturnStatement):
        _walk_expr(stmt.expression, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.ThrowStatement):
        _walk_expr(stmt.expression, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.StatementExpression):
        _walk_expr(stmt.expression, source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.LocalVariableDeclaration):
        for d in stmt.declarators or []:
            _walk_expr(getattr(d, "initializer", None), source, caller, fr, cond_stack)
        return
    if isinstance(stmt, javalang.tree.AssertStatement):
        _walk_expr(stmt.condition, source, caller, fr, cond_stack)
        _walk_expr(stmt.value, source, caller, fr, cond_stack)
        return


class JavaParser:
    language = "java"

    @staticmethod
    def _format_invocation_static(expr: object) -> str:
        return _format_invocation(expr)

    @staticmethod
    def _resolution_static(expr: object) -> CallResolution:
        return _resolution_for_invocation(expr)

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        import javalang
        from javalang.tree import MethodDeclaration

        root = project_root.resolve()
        key = _rel_key(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        fr = FileParseResult(path=path.resolve(), language=self.language)

        try:
            tree = javalang.parse.parse(text)
        except Exception:
            return fr

        for t in tree.types or []:
            cls_name = getattr(t, "name", None)
            if not cls_name:
                continue
            for m in getattr(t, "methods", None) or []:
                if not isinstance(m, MethodDeclaration):
                    continue
                caller = _sid(key, cls_name, m.name)
                fr.symbol_ids.append(caller)
                body = m.body
                if isinstance(body, javalang.tree.BlockStatement):
                    _walk_block(body.statements or [], text, caller, fr, [])
                elif isinstance(body, list):
                    _walk_block(body, text, caller, fr, [])
                elif body is not None:
                    _walk_stmt(body, text, caller, fr, [])

                ann_text = " ".join(str(getattr(a, "name", a)) for a in (getattr(m, "annotations", None) or []))
                if "KafkaListener" in ann_text or "kafka" in ann_text.lower():
                    pos = getattr(m, "position", None)
                    line = int(getattr(pos, "line", 0) or 0) if pos else 0
                    fr.entries.append(
                        EntryRecord(
                            symbol_id=caller,
                            kind=EntryKind.KAFKA,
                            label="Kafka listener",
                            file_path=str(path.resolve()),
                            line=line,
                        ),
                    )

        return fr
