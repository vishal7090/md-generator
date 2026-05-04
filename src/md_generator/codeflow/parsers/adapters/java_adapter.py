"""javalang method bodies → IRMethod / IRStmt."""

from __future__ import annotations

from pathlib import Path

import javalang.tree

from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sid(key: str, fq_class: str, name: str) -> str:
    return f"{key}::{fq_class}.{name}"


def _line(node: object) -> int | None:
    pos = getattr(node, "position", None)
    if pos:
        ln = int(getattr(pos, "line", None) or 0)
        return ln if ln else None
    return None


def _stmt_items(st: object | None) -> list:
    if st is None:
        return []
    if isinstance(st, list):
        return st
    if isinstance(st, javalang.tree.BlockStatement):
        return list(st.statements or [])
    return [st]


def _stmt_list(stmts: list | None) -> tuple[IRStmt, ...]:
    if not stmts:
        return ()
    out: list[IRStmt] = []
    for s in stmts:
        ir = _java_stmt(s)
        if ir is not None:
            out.append(ir)
    return tuple(out)


def _java_stmt(node: object) -> IRStmt | None:
    if isinstance(node, javalang.tree.IfStatement):
        then_items = _stmt_items(getattr(node, "then_statement", None))
        else_items = _stmt_items(getattr(node, "else_statement", None))
        return IRStmt(
            kind="IF",
            condition=str(getattr(node, "condition", ""))[:200],
            body=_stmt_list(then_items),
            else_body=_stmt_list(else_items),
            line=_line(node),
        )
    if isinstance(node, javalang.tree.WhileStatement):
        body_items = _stmt_items(getattr(node, "body", None))
        return IRStmt(
            kind="LOOP",
            condition=str(getattr(node, "condition", "") or "while")[:200],
            body=_stmt_list(list(body_items)),
            line=_line(node),
        )
    if isinstance(node, javalang.tree.ForStatement):
        body_items = _stmt_items(getattr(node, "body", None))
        return IRStmt(
            kind="LOOP",
            condition="for",
            body=_stmt_list(list(body_items)),
            line=_line(node),
        )
    if isinstance(node, javalang.tree.DoStatement):
        body_items = _stmt_items(getattr(node, "body", None))
        return IRStmt(
            kind="LOOP",
            condition=str(getattr(node, "condition", "") or "do-while")[:200],
            body=_stmt_list(list(body_items)),
            line=_line(node),
        )
    if isinstance(node, javalang.tree.TryStatement):
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        for ct in getattr(node, "catches", None) or []:
            types = getattr(getattr(ct, "parameter", None), "types", None) or []
            lab = "except:" + "/".join(str(x) for x in types) if types else "except"
            cases.append((lab, _stmt_list(ct.block)))
        fin = list(getattr(node, "finally_block", None) or [])
        return IRStmt(
            kind="TRY",
            body=_stmt_list(list(getattr(node, "block", None) or [])),
            cases=tuple(cases),
            else_body=_stmt_list(fin),
            line=_line(node),
        )
    if isinstance(node, javalang.tree.SwitchStatement):
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        for c in getattr(node, "cases", None) or []:
            lab = str(getattr(c, "case", None) or "case")[:80]
            cases.append((lab, _stmt_list(list(getattr(c, "statements", None) or []))))
        return IRStmt(
            kind="SWITCH",
            condition=str(getattr(node, "expression", ""))[:200],
            cases=tuple(cases),
            line=_line(node),
        )
    if isinstance(node, javalang.tree.StatementExpression):
        expr = node.expression
        if isinstance(expr, javalang.tree.MethodInvocation):
            return IRStmt(
                kind="CALL",
                target=str(getattr(expr, "member", "") or ""),
                label="call",
                line=_line(node),
            )
    if isinstance(node, javalang.tree.LocalVariableDeclaration):
        for d in getattr(node, "declarators", None) or []:
            init = getattr(d, "initializer", None)
            if isinstance(init, javalang.tree.MethodInvocation):
                return IRStmt(
                    kind="CALL",
                    target=str(getattr(init, "member", "") or ""),
                    label="var",
                    line=_line(node),
                )
    if isinstance(node, javalang.tree.ReturnStatement):
        expr = getattr(node, "value", None)
        if isinstance(expr, javalang.tree.MethodInvocation):
            return IRStmt(
                kind="CALL",
                target=str(getattr(expr, "member", "") or ""),
                label="return",
                line=_line(node),
            )
        return IRStmt(kind="RETURN", label="return", line=_line(node))
    if isinstance(node, javalang.tree.BlockStatement):
        inner = _stmt_list(list(node.statements or []))
        if not inner:
            return None
        if len(inner) == 1:
            return inner[0]
        return IRStmt(kind="STATEMENT", label="block", body=inner, line=_line(node))
    return IRStmt(kind="STATEMENT", label=type(node).__name__, line=_line(node))


def _iter_methods_in_type(cdecl: object, prefix: tuple[str, ...], key: str, fp: str, out: list[IRMethod]) -> None:
    name = getattr(cdecl, "name", None) or ""
    parts = prefix + (name,)
    fq = ".".join(parts)
    for m in getattr(cdecl, "methods", None) or []:
        if not isinstance(m, javalang.tree.MethodDeclaration):
            continue
        body_stmts = list(getattr(getattr(m, "body", None), "statements", None) or [])
        body = _stmt_list(body_stmts)
        sid = _sid(key, fq, m.name)
        out.append(IRMethod(symbol_id=sid, name=m.name, file_path=fp, language="java", body=body))
    for item in getattr(cdecl, "body", None) or []:
        if isinstance(item, javalang.tree.ClassDeclaration):
            _iter_methods_in_type(item, parts, key, fp, out)


def populate_ir_methods_java(fr: FileParseResult, project_root: Path) -> None:
    if not str(fr.path).endswith(".java"):
        fr.ir_methods = []
        return
    text = fr.path.read_text(encoding="utf-8", errors="replace")
    try:
        import javalang

        tree = javalang.parse.parse(text)
    except Exception:
        fr.ir_methods = []
        return
    key = _rel_key(fr.path, project_root.resolve())
    fp = str(fr.path.resolve())
    out: list[IRMethod] = []
    for top in tree.types or []:
        if isinstance(top, javalang.tree.ClassDeclaration):
            _iter_methods_in_type(top, (), key, fp, out)
    fr.ir_methods = out
