from __future__ import annotations

from pathlib import Path

import javalang.tree

from md_generator.codeflow.graph.relations import REL_IMPLEMENTS, REL_IMPORTS, REL_INHERITS
from md_generator.codeflow.models.ir import (
    BranchPoint,
    CallSite,
    CallResolution,
    EntryKind,
    EntryRecord,
    FileParseResult,
    StructuralEdge,
)


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sid(key: str, cls: str, method: str) -> str:
    return f"{key}::{cls}.{method}"


def _reference_type_fqn(rt: object) -> str:
    parts: list[str] = []
    cur: object | None = rt
    while cur is not None:
        parts.append(str(getattr(cur, "name", "") or ""))
        cur = getattr(cur, "sub_type", None)
    return ".".join(parts)


def _qualify_java_type(simple_or_fqn: str, java_package: str) -> str:
    s = (simple_or_fqn or "").strip()
    if not s:
        return s
    if "." in s:
        return s
    pkg = (java_package or "").strip()
    return f"{pkg}.{s}" if pkg else s


def _emit_compilation_unit_imports(tree: object, key: str, fr: FileParseResult) -> None:
    fid = f"file:{key}"
    for imp in getattr(tree, "imports", None) or []:
        if getattr(imp, "wildcard", False):
            continue
        if getattr(imp, "static", False):
            continue
        path = getattr(imp, "path", None)
        if not path or not isinstance(path, str):
            continue
        fr.structural_edges.append(
            StructuralEdge(
                source_id=fid,
                target_id=f"external::{path}",
                relation=REL_IMPORTS,
                confidence=0.7,
                line=None,
            ),
        )


def _emit_type_inheritance(key: str, fq_class: str, decl: object, java_package: str, fr: FileParseResult) -> None:
    cid = f"class:{key}::{fq_class}"
    ex = getattr(decl, "extends", None)
    if ex is not None:
        raw = _reference_type_fqn(ex)
        tgt = _qualify_java_type(raw, java_package)
        if tgt:
            fr.structural_edges.append(
                StructuralEdge(
                    source_id=cid,
                    target_id=f"external::{tgt}",
                    relation=REL_INHERITS,
                    confidence=0.7,
                    line=None,
                ),
            )
    for impl in getattr(decl, "implements", None) or []:
        raw = _reference_type_fqn(impl)
        tgt = _qualify_java_type(raw, java_package)
        if tgt:
            fr.structural_edges.append(
                StructuralEdge(
                    source_id=cid,
                    target_id=f"external::{tgt}",
                    relation=REL_IMPLEMENTS,
                    confidence=0.7,
                    line=None,
                ),
            )


def _parse_type_declaration(
    decl: object,
    key: str,
    fq_class: str,
    text: str,
    fr: FileParseResult,
) -> None:
    """Walk one class/interface/enum declaration and nested types; emit methods and calls."""
    import javalang
    from javalang.tree import ClassDeclaration, MethodDeclaration

    _emit_type_inheritance(key, fq_class, decl, fr.java_package or "", fr)

    for item in getattr(decl, "body", None) or []:
        if isinstance(item, ClassDeclaration):
            _parse_type_declaration(item, key, f"{fq_class}.{item.name}", text, fr)

    for m in getattr(decl, "methods", None) or []:
        if not isinstance(m, MethodDeclaration):
            continue
        caller = _sid(key, fq_class, m.name)
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
                    file_path=str(fr.path),
                    line=line,
                ),
            )


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

        root = project_root.resolve()
        key = _rel_key(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        fr = FileParseResult(path=path.resolve(), language=self.language)

        try:
            tree = javalang.parse.parse(text)
        except Exception:
            return fr

        fr.java_package = tree.package.name if tree.package else None
        _emit_compilation_unit_imports(tree, key, fr)

        from javalang.tree import ClassDeclaration, EnumDeclaration, InterfaceDeclaration

        for t in tree.types or []:
            name = getattr(t, "name", None)
            if not name:
                continue
            if isinstance(t, (ClassDeclaration, InterfaceDeclaration, EnumDeclaration)):
                _parse_type_declaration(t, key, name, text, fr)

        return fr
