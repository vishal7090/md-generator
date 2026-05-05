"""C/C++: Tree-sitter-cpp → ``IRMethod`` (optional ``tree-sitter-cpp`` extra)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sid(key: str, name: str) -> str:
    return f"{key}::{name}"


def _text(source: bytes, node: Any) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _trim(s: str, max_len: int = 160) -> str:
    s = " ".join(s.split())
    return s[:max_len] if len(s) <= max_len else s[: max_len - 1] + "…"


def _call_target(node: Any, source: bytes) -> str:
    fn = node.child_by_field_name("function")
    if fn:
        return _trim(_text(source, fn))
    return "call"


def _stmt_list_from_compound(block: Any, source: bytes) -> tuple[IRStmt, ...]:
    if block is None or block.type != "compound_statement":
        return ()
    out: list[IRStmt] = []
    for ch in block.named_children:
        ir = _cpp_stmt(ch, source)
        if ir is not None:
            out.append(ir)
    return tuple(out)


def _stmt_list_from_statement(st: Any, source: bytes) -> tuple[IRStmt, ...]:
    if st is None:
        return ()
    if st.type == "compound_statement":
        return _stmt_list_from_compound(st, source)
    ir = _cpp_stmt(st, source)
    return (ir,) if ir is not None else ()


def _cpp_stmt(node: Any, source: bytes) -> IRStmt | None:
    t = node.type
    if t == "if_statement":
        cond_n = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt_clause = node.child_by_field_name("alternative")
        cond_txt = _trim(_text(source, cond_n)) if cond_n else "if"
        then_body = _stmt_list_from_statement(cons, source)
        else_body: tuple[IRStmt, ...] = ()
        if alt_clause is not None:
            for ch in alt_clause.named_children:
                if ch.type in ("compound_statement", "if_statement"):
                    else_body = _stmt_list_from_statement(ch, source)
                    break
        return IRStmt(
            kind="IF",
            condition=cond_txt,
            body=then_body,
            else_body=else_body,
            line=node.start_point[0] + 1,
        )
    if t in ("for_statement", "while_statement", "do_statement"):
        cond_n = node.child_by_field_name("condition")
        body_n = node.child_by_field_name("body")
        cond_txt = _trim(_text(source, cond_n)) if cond_n else t
        blk = body_n if body_n and body_n.type == "compound_statement" else None
        if body_n and body_n.type != "compound_statement":
            inner = _stmt_list_from_statement(body_n, source)
        else:
            inner = _stmt_list_from_compound(blk, source)
        return IRStmt(
            kind="LOOP",
            condition=cond_txt,
            body=inner,
            line=node.start_point[0] + 1,
        )
    if t == "switch_statement":
        cond_n = node.child_by_field_name("condition")
        disc = _trim(_text(source, cond_n)) if cond_n else "switch"
        body = node.child_by_field_name("body")
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        if body and body.type == "compound_statement":
            for ch in body.named_children:
                if ch.type != "case_statement":
                    continue
                lab = _trim(_text(source, ch), 120)
                stmts: list[IRStmt] = []
                for sub in ch.named_children:
                    if sub.type in ("case", "default", ":", "char_literal"):
                        continue
                    if sub.type == "expression_statement" or sub.type.endswith("_statement"):
                        ir = _cpp_stmt(sub, source)
                        if ir:
                            stmts.append(ir)
                cases.append((lab, tuple(stmts)))
        return IRStmt(
            kind="SWITCH",
            condition=disc,
            cases=tuple(cases),
            line=node.start_point[0] + 1,
        )
    if t == "try_statement":
        body = node.child_by_field_name("body")
        try_body = _stmt_list_from_compound(body, source)
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        for ch in node.named_children:
            if ch.type != "catch_clause":
                continue
            params = ch.child_by_field_name("parameters")
            lab = _trim(_text(source, params)) if params else "catch"
            cb = ch.child_by_field_name("body")
            cases.append((lab, _stmt_list_from_compound(cb, source)))
        return IRStmt(
            kind="TRY",
            body=try_body,
            cases=tuple(cases),
            else_body=(),
            line=node.start_point[0] + 1,
        )
    if t == "break_statement":
        return IRStmt(kind="BREAK", line=node.start_point[0] + 1)
    if t == "continue_statement":
        return IRStmt(kind="CONTINUE", line=node.start_point[0] + 1)
    if t == "return_statement":
        inner = _trim(_text(source, node))
        return IRStmt(kind="RETURN", label=inner if inner else "return", line=node.start_point[0] + 1)
    if t == "expression_statement":
        for ch in node.named_children:
            if ch.type == "call_expression":
                return IRStmt(
                    kind="CALL",
                    target=_call_target(ch, source),
                    label="call",
                    line=node.start_point[0] + 1,
                )
        return IRStmt(
            kind="STATEMENT",
            label=_trim(_text(source, node)),
            line=node.start_point[0] + 1,
        )
    if t == "declaration":
        return IRStmt(kind="STATEMENT", label=_trim(_text(source, node), 120), line=node.start_point[0] + 1)
    return IRStmt(kind="STATEMENT", label=t, line=node.start_point[0] + 1)


def _fn_name_from_declarator(decl: Any, source: bytes) -> str:
    if decl is None:
        return "<fn>"
    raw = _text(source, decl).strip()
    if "(" in raw:
        head = raw.split("(", 1)[0].strip()
        return head.split()[-1] if head else "<fn>"
    return raw.split()[-1] if raw else "<fn>"


def _collect_from_node(
    node: Any,
    source: bytes,
    key: str,
    fp: str,
    lang: str,
    class_name: str | None,
    out: list[IRMethod],
) -> None:
    t = node.type
    if t == "function_definition":
        decl = node.child_by_field_name("declarator")
        fn_name = _fn_name_from_declarator(decl, source)
        body = node.child_by_field_name("body")
        stmts = _stmt_list_from_compound(body, source) if body else ()
        sid = _sid(key, f"{class_name}.{fn_name}" if class_name else fn_name)
        out.append(IRMethod(symbol_id=sid, name=fn_name, file_path=fp, language=lang, body=stmts))
        return
    if t == "class_specifier":
        nm_node = node.child_by_field_name("name")
        cname = _text(source, nm_node).strip() if nm_node else "Class"
        body = node.child_by_field_name("body")
        if body:
            for ch in body.named_children:
                _collect_from_node(ch, source, key, fp, lang, cname, out)
        return
    if t == "translation_unit" or t == "declaration":
        for ch in node.named_children:
            _collect_from_node(ch, source, key, fp, lang, class_name, out)
        return
    for ch in node.named_children:
        _collect_from_node(ch, source, key, fp, lang, class_name, out)


def populate_ir_methods_cpp(fr: FileParseResult, project_root: Path) -> None:
    try:
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser
    except ImportError:
        fr.ir_methods = []
        return
    try:
        lang = Language(tscpp.language())
        parser = Parser(lang)
        source = fr.path.read_bytes()
        tree = parser.parse(source)
    except OSError:
        fr.ir_methods = []
        return
    key = _rel_key(fr.path, project_root.resolve())
    fp = str(fr.path.resolve())
    out: list[IRMethod] = []
    _collect_from_node(tree.root_node, source, key, fp, fr.language or "cpp", None, out)
    fr.ir_methods = out
