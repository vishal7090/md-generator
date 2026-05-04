"""Tree-sitter JS/TS/TSX → IRMethod (optional tree-sitter deps)."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Language, Node, Parser

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


def _text(source: bytes, node: Node | None) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _trim(s: str, max_len: int = 160) -> str:
    s = " ".join(s.split())
    return s[:max_len] if len(s) <= max_len else s[: max_len - 1] + "…"


def _call_name(node: Node, source: bytes) -> str:
    fn = node.child_by_field_name("function")
    if fn:
        return _trim(_text(source, fn))
    return "call"


def _stmt_list_from_block(block: Node | None, source: bytes) -> tuple[IRStmt, ...]:
    if block is None:
        return ()
    out: list[IRStmt] = []
    for ch in block.named_children:
        ir = _ts_stmt(ch, source)
        if ir is not None:
            out.append(ir)
    return tuple(out)


def _ts_stmt(node: Node, source: bytes) -> IRStmt | None:
    t = node.type
    if t == "if_statement":
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        then_body = _stmt_list_from_block(cons if cons and cons.type == "statement_block" else None, source)
        if cons and cons.type != "statement_block":
            ir = _ts_stmt(cons, source)
            then_body = (ir,) if ir else ()
        else_body = ()
        if alt:
            if alt.type == "statement_block":
                else_body = _stmt_list_from_block(alt, source)
            else:
                eir = _ts_stmt(alt, source)
                else_body = (eir,) if eir else ()
        return IRStmt(
            kind="IF",
            condition=_trim(_text(source, cond)) if cond else "if",
            body=then_body,
            else_body=else_body,
            line=node.start_point[0] + 1,
        )
    if t in ("for_statement", "while_statement", "do_statement"):
        cond = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        blk = body if body and body.type == "statement_block" else None
        return IRStmt(
            kind="LOOP",
            condition=_trim(_text(source, cond)) if cond else t,
            body=_stmt_list_from_block(blk, source),
            line=node.start_point[0] + 1,
        )
    if t == "switch_statement":
        disc = node.child_by_field_name("value")
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        for ch in node.named_children:
            if ch.type != "switch_body":
                continue
            for case in ch.named_children:
                if case.type != "switch_case":
                    continue
                lab = _trim(_text(source, case))[:80]
                stmts: list[IRStmt] = []
                for sub in case.named_children:
                    ir = _ts_stmt(sub, source)
                    if ir:
                        stmts.append(ir)
                cases.append((lab, tuple(stmts)))
        return IRStmt(
            kind="SWITCH",
            condition=_trim(_text(source, disc)) if disc else "switch",
            cases=tuple(cases),
            line=node.start_point[0] + 1,
        )
    if t == "try_statement":
        body = node.child_by_field_name("body")
        try_body = _stmt_list_from_block(body, source) if body else ()
        cases: list[tuple[str, tuple[IRStmt, ...]]] = []
        fin: tuple[IRStmt, ...] = ()
        for ch in node.named_children:
            if ch.type == "catch_clause":
                p = ch.child_by_field_name("parameter")
                lab = _trim(_text(source, p)) if p else "catch"
                b = ch.child_by_field_name("body")
                cases.append((lab, _stmt_list_from_block(b, source)))
            elif ch.type == "finally_clause":
                b = ch.child_by_field_name("body")
                fin = _stmt_list_from_block(b, source)
        return IRStmt(
            kind="TRY",
            body=try_body,
            cases=tuple(cases),
            else_body=fin,
            line=node.start_point[0] + 1,
        )
    if t == "expression_statement":
        for ch in node.named_children:
            if ch.type == "call_expression":
                return IRStmt(
                    kind="CALL",
                    target=_call_name(ch, source),
                    label="call",
                    line=node.start_point[0] + 1,
                )
    if t == "return_statement":
        for ch in node.named_children:
            if ch.type == "call_expression":
                return IRStmt(
                    kind="CALL",
                    target=_call_name(ch, source),
                    label="return",
                    line=node.start_point[0] + 1,
                )
        return IRStmt(kind="RETURN", label="return", line=node.start_point[0] + 1)
    return IRStmt(kind="STATEMENT", label=t, line=node.start_point[0] + 1)


def _method_name_from_declaration(node: Node, source: bytes) -> str:
    decl = node.child_by_field_name("name")
    if decl:
        return _text(source, decl).strip() or "fn"
    return "fn"


def _collect_ir_from_node(node: Node, source: bytes, key: str, fp: str, lang: str, class_name: str | None, out: list[IRMethod]) -> None:
    if node.type in ("function_declaration", "generator_function_declaration"):
        name = _method_name_from_declaration(node, source)
        body = node.child_by_field_name("body")
        stmts = _stmt_list_from_block(body, source) if body else ()
        sid = _sid(key, class_name, name)
        out.append(IRMethod(symbol_id=sid, name=name, file_path=fp, language=lang, body=stmts))
        return
    if node.type == "method_definition":
        nm = node.child_by_field_name("name")
        name = _text(source, nm).strip() if nm else "method"
        body = node.child_by_field_name("body")
        stmts = _stmt_list_from_block(body, source) if body else ()
        sid = _sid(key, class_name, name)
        out.append(IRMethod(symbol_id=sid, name=name, file_path=fp, language=lang, body=stmts))
        return
    if node.type == "class_declaration":
        nm = node.child_by_field_name("name")
        cname = _text(source, nm).strip() if nm else "Class"
        body = node.child_by_field_name("body")
        if body:
            for ch in body.children:
                _collect_ir_from_node(ch, source, key, fp, lang, cname, out)
        return
    for ch in node.children:
        _collect_ir_from_node(ch, source, key, fp, lang, class_name, out)


def _language_for_fr(fr: FileParseResult) -> Language | None:
    if fr.language == "javascript":
        import tree_sitter_javascript as tsjs

        return Language(tsjs.language())
    if fr.language == "typescript":
        import tree_sitter_typescript as tsts

        return Language(tsts.language_typescript())
    if fr.language == "tsx":
        import tree_sitter_typescript as tsts

        return Language(tsts.language_tsx())
    return None


def populate_ir_methods_treesitter(fr: FileParseResult, project_root: Path) -> None:
    lang = _language_for_fr(fr)
    if lang is None:
        fr.ir_methods = []
        return
    source = fr.path.read_bytes()
    parser = Parser(lang)
    tree = parser.parse(source)
    key = _rel_key(fr.path, project_root.resolve())
    fp = str(fr.path.resolve())
    out: list[IRMethod] = []
    _collect_ir_from_node(tree.root_node, source, key, fp, fr.language, None, out)
    fr.ir_methods = out
