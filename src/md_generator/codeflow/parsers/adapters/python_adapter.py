"""Python ast → IRMethod / IRStmt (IR types only from models.ir_cfg)."""

from __future__ import annotations

import ast
from pathlib import Path

from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sid(key: str, cls: str | None, name: str) -> str:
    if cls:
        return f"{key}::{cls}.{name}"
    return f"{key}::{name}"


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node).replace("\n", " ")[:200]
    except Exception:
        return type(node).__name__


def normalize_stmt(node: ast.stmt) -> IRStmt | None:
    if isinstance(node, ast.If):
        then_body = tuple(_stmt_list(node.body))
        else_body = tuple(_stmt_list(node.orelse))
        return IRStmt(
            kind="IF",
            condition=_unparse(node.test),
            body=then_body,
            else_body=else_body,
            line=getattr(node, "lineno", None),
        )
    if isinstance(node, (ast.For, ast.AsyncFor)):
        cond = _unparse(node.iter) if isinstance(node, ast.For) else "async_for"
        return IRStmt(
            kind="LOOP",
            condition=cond,
            body=tuple(_stmt_list(node.body)),
            line=getattr(node, "lineno", None),
        )
    if isinstance(node, ast.While):
        return IRStmt(
            kind="LOOP",
            condition=_unparse(node.test),
            body=tuple(_stmt_list(node.body)),
            line=getattr(node, "lineno", None),
        )
    if isinstance(node, ast.Try):
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        for h in node.handlers:
            lab = "except"
            if h.type:
                lab = f"except:{_unparse(h.type)}"
            cases.append((lab, tuple(_stmt_list(h.body))))
        fin = tuple(_stmt_list(node.finalbody)) if node.finalbody else ()
        return IRStmt(
            kind="TRY",
            body=tuple(_stmt_list(node.body)),
            cases=tuple(cases),
            else_body=fin,
            line=getattr(node, "lineno", None),
        )
    if isinstance(node, ast.Match):
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        for c in node.cases:
            pat = _unparse(c.pattern) if c.pattern else "case"
            cases.append((pat, tuple(_stmt_list(c.body))))
        return IRStmt(
            kind="SWITCH",
            condition=_unparse(node.subject),
            cases=tuple(cases),
            line=getattr(node, "lineno", None),
        )
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        tgt = _call_target(node.value)
        return IRStmt(kind="CALL", target=tgt, label="call", line=getattr(node, "lineno", None))
    if isinstance(node, ast.Assign):
        if isinstance(node.value, ast.Call):
            return IRStmt(
                kind="CALL",
                target=_call_target(node.value),
                label=_unparse(node),
                line=getattr(node, "lineno", None),
            )
    if isinstance(node, ast.AnnAssign) and node.value and isinstance(node.value, ast.Call):
        return IRStmt(
            kind="CALL",
            target=_call_target(node.value),
            label=_unparse(node),
            line=getattr(node, "lineno", None),
        )
    if isinstance(node, ast.Return):
        if node.value and isinstance(node.value, ast.Call):
            return IRStmt(
                kind="CALL",
                target=_call_target(node.value),
                label="return",
                line=getattr(node, "lineno", None),
            )
        return IRStmt(
            kind="RETURN",
            label=_unparse(node.value) if node.value else "return",
            line=getattr(node, "lineno", None),
        )
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    return IRStmt(kind="STATEMENT", label=_unparse(node)[:120], line=getattr(node, "lineno", None))


def _stmt_list(nodes: list[ast.stmt]) -> list[IRStmt]:
    out: list[IRStmt] = []
    for s in nodes:
        ir = normalize_stmt(s)
        if ir is not None:
            out.append(ir)
    return out


def _call_target(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts: list[str] = []
        cur: ast.expr = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return "call"


def normalize_python_method(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    file_key: str,
    file_path: str,
    class_name: str | None,
) -> IRMethod:
    name = fn.name
    sid = _sid(file_key, class_name, name)
    body = tuple(_stmt_list(fn.body))
    return IRMethod(symbol_id=sid, name=name, file_path=file_path, language="python", body=body)


def populate_ir_methods_python(fr: FileParseResult, project_root: Path) -> None:
    """Fill ``fr.ir_methods`` from the file (re-parse)."""
    root = project_root.resolve()
    key = _rel_key(fr.path, root)
    text = fr.path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=str(fr.path))
    except SyntaxError:
        fr.ir_methods = []
        return
    out: list[IRMethod] = []
    fp = str(fr.path.resolve())

    class_stack: list[str] = []

    def visit_class(cls: ast.ClassDef) -> None:
        class_stack.append(cls.name)
        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append(normalize_python_method(node, file_key=key, file_path=fp, class_name=cls.name))
            elif isinstance(node, ast.ClassDef):
                visit_class(node)
        class_stack.pop()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            visit_class(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(normalize_python_method(node, file_key=key, file_path=fp, class_name=None))

    fr.ir_methods = out
