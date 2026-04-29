"""JavaScript / TypeScript / TSX parsing via Tree-sitter."""

from __future__ import annotations

import logging
from pathlib import Path

from tree_sitter import Language, Node, Parser

from md_generator.codeflow.models.ir import (
    BranchPoint,
    BusinessRule,
    CallSite,
    CallResolution,
    FileParseResult,
)

logger = logging.getLogger(__name__)


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _text(source: bytes, node: Node | None) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _trim(s: str, max_len: int = 120) -> str:
    s = " ".join(s.split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _sid(key: str, cls: str | None, name: str) -> str:
    if cls:
        return f"{key}::{cls}.{name}"
    return f"{key}::{name}"


def _call_resolution(callee: str) -> CallResolution:
    c = callee.strip().replace(" ", "")
    if c.isidentifier():
        return "static"
    if "." in c and all(part.isidentifier() for part in c.split(".") if part):
        return "static"
    return "dynamic"


def _enclosing_condition_label(source: bytes, call: Node) -> str | None:
    cur: Node | None = getattr(call, "parent", None)
    while cur is not None:
        t = cur.type
        if t == "if_statement":
            cond = cur.child_by_field_name("condition")
            if cond:
                return _trim(_text(source, cond))
            return "if (…)"
        if t == "while_statement":
            cond = cur.child_by_field_name("condition")
            if cond:
                return _trim(_text(source, cond))
            return "while (…)"
        if t == "for_statement":
            cond = cur.child_by_field_name("condition")
            if cond:
                return _trim(_text(source, cond))
            return "for (…)"
        if t == "do_statement":
            cond = cur.child_by_field_name("condition")
            if cond:
                return _trim(_text(source, cond))
            return "do … while"
        if t == "ternary_expression":
            cond = cur.child_by_field_name("condition")
            if cond:
                return _trim(_text(source, cond))
            return "… ? … : …"
        if t == "switch_case":
            parts: list[str] = []
            for ch in cur.children:
                if ch.type == "default":
                    return "default:"
                if ch.type == ":":
                    break
                if ch.type not in ("case",):
                    parts.append(_text(source, ch).strip())
            if parts:
                return _trim("case " + " ".join(parts))
            return "case …"
        if t in (
            "function_declaration",
            "method_definition",
            "generator_function_declaration",
            "arrow_function",
            "function_expression",
            "program",
        ):
            break
        cur = getattr(cur, "parent", None)
    return None


def _fn_boundary_types() -> frozenset[str]:
    return frozenset(
        {
            "function_declaration",
            "method_definition",
            "generator_function_declaration",
            "arrow_function",
            "function_expression",
        },
    )


def _collect_js_ts_validation_and_branches(
    root: Node,
    source: bytes,
    file_key: str,
    fr: FileParseResult,
) -> None:
    """Populate ``fr.rules`` (throw/assert) and ``fr.branches`` (if/switch) using a scoped walk."""

    def fn_id_for_decl(
        node: Node,
        outer_class: str | None,
    ) -> str | None:
        t = node.type
        if t in ("function_declaration", "generator_function_declaration"):
            name_node = node.child_by_field_name("name")
            raw = _text(source, name_node).strip() if name_node else ""
            nm = raw or "<anonymous>"
            return _sid(file_key, outer_class, nm)
        if t == "method_definition":
            name_node = node.child_by_field_name("name")
            raw = _text(source, name_node).strip() if name_node else ""
            nm = raw or "<anonymous>"
            cls = outer_class or "anon"
            return _sid(file_key, cls, nm)
        if t == "arrow_function":
            return _sid(file_key, outer_class, "<arrow>")
        if t == "function_expression":
            return _sid(file_key, outer_class, "<function_expr>")
        return None

    stack: list[str | None] = []
    class_stack: list[str | None] = [None]

    def visit(node: Node) -> None:
        t = node.type
        if t == "class_declaration":
            nm_node = node.child_by_field_name("name")
            nm = _text(source, nm_node).strip() or "anon"
            class_stack.append(nm)
            for c in node.children:
                visit(c)
            class_stack.pop()
            return
        if t in _fn_boundary_types():
            fid = fn_id_for_decl(node, class_stack[-1])
            if fid:
                stack.append(fid)
            body = node.child_by_field_name("body")
            if body:
                for c in body.children:
                    visit(c)
            elif t == "arrow_function":
                body = node.child_by_field_name("body")
                if body:
                    visit(body)
            if fid:
                stack.pop()
            return
        if t == "if_statement" and stack and stack[-1]:
            cond = node.child_by_field_name("condition")
            lab = _trim(_text(source, cond)) if cond else "if (…)"
            ln = node.start_point[0] + 1
            fr.branches.append(
                BranchPoint(caller_id=stack[-1], kind="if", label=lab, line=ln),
            )
        if t == "switch_statement" and stack and stack[-1]:
            for ch in node.children:
                if ch.type != "switch_body":
                    continue
                for case in ch.children:
                    if case.type == "switch_default":
                        fr.branches.append(
                            BranchPoint(
                                caller_id=stack[-1],
                                kind="switch",
                                label="default:",
                                line=case.start_point[0] + 1,
                            ),
                        )
                        continue
                    if case.type != "switch_case":
                        continue
                    bits: list[str] = []
                    for x in case.children:
                        if x.type == ":":
                            break
                        if x.type != "case":
                            bits.append(_text(source, x).strip())
                    lab = _trim("case " + " ".join(bits)) if bits else "case …"
                    fr.branches.append(
                        BranchPoint(
                            caller_id=stack[-1],
                            kind="switch",
                            label=lab,
                            line=case.start_point[0] + 1,
                        ),
                    )
        if t == "throw_statement" and stack and stack[-1]:
            arg = node.child_by_field_name("argument")
            det = _trim(_text(source, arg)) if arg else "throw"
            ln = node.start_point[0] + 1
            fp = str(fr.path)
            fr.rules.append(
                BusinessRule(
                    source="validation",
                    symbol_id=stack[-1],
                    file_path=fp,
                    line=ln,
                    title="Throw",
                    detail=det,
                    confidence="medium",
                ),
            )
        if t == "expression_statement" and stack and stack[-1]:
            expr = node.child_by_field_name("expression")
            if expr and expr.type == "call_expression":
                fn = expr.child_by_field_name("function")
                callee = _text(source, fn).strip().replace("\n", " ") if fn else ""
                if callee in ("assert", "console.assert", "assert.strictEqual", "assert.equal"):
                    args = expr.child_by_field_name("arguments")
                    det = _trim(_text(source, args) if args else callee)
                    ln = expr.start_point[0] + 1
                    fr.rules.append(
                        BusinessRule(
                            source="validation",
                            symbol_id=stack[-1],
                            file_path=str(fr.path),
                            line=ln,
                            title=f"Assert `{callee}`",
                            detail=det,
                            confidence="low",
                        ),
                    )
        for c in node.children:
            visit(c)

    visit(root)


class TreesitterJsTsParser:
    """Parses ``.js``/``.jsx``/``.mjs`` or ``.ts``/``.mts`` or ``.tsx`` using Tree-sitter."""

    def __init__(self, language_key: str, language: Language) -> None:
        self.language = language_key
        self._language = language

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        fr = FileParseResult(path=path.resolve(), language=self.language)
        source = path.read_bytes()
        parser = Parser(self._language)
        tree = parser.parse(source)
        if tree.root_node.has_error:
            logger.debug("tree-sitter parse has errors: %s", path)
        key = _rel_key(path, project_root)
        self._walk(tree.root_node, source, key, fr, class_name=None, current_fn=None)
        _collect_js_ts_validation_and_branches(tree.root_node, source, key, fr)
        return fr

    def _walk(
        self,
        node: Node,
        source: bytes,
        file_key: str,
        fr: FileParseResult,
        *,
        class_name: str | None,
        current_fn: str | None,
    ) -> None:
        t = node.type
        if t == "class_declaration":
            nm = _text(source, node.child_by_field_name("name")).strip() or "anon"
            body = node.child_by_field_name("body")
            if body:
                for ch in body.children:
                    self._walk(ch, source, file_key, fr, class_name=nm, current_fn=current_fn)
            return
        if t in ("function_declaration", "method_definition", "generator_function_declaration"):
            name_node = node.child_by_field_name("name")
            raw_name = _text(source, name_node).strip() if name_node else ""
            nm = raw_name or "<anonymous>"
            fid = _sid(file_key, class_name, nm)
            if fid not in fr.symbol_ids:
                fr.symbol_ids.append(fid)
            body = node.child_by_field_name("body")
            if body:
                for ch in body.children:
                    self._walk(ch, source, file_key, fr, class_name=class_name, current_fn=fid)
            return
        if t == "arrow_function":
            fid = _sid(file_key, class_name, "<arrow>")
            if fid not in fr.symbol_ids:
                fr.symbol_ids.append(fid)
            body = node.child_by_field_name("body")
            if body and body.type == "statement_block":
                for ch in body.children:
                    self._walk(ch, source, file_key, fr, class_name=class_name, current_fn=fid)
            elif body:
                self._walk(body, source, file_key, fr, class_name=class_name, current_fn=fid)
            return
        if t == "call_expression" and current_fn:
            fn = node.child_by_field_name("function")
            callee = _text(source, fn).strip().replace("\n", " ")
            if len(callee) > 200:
                callee = callee[:197] + "..."
            line = node.start_point[0] + 1
            cond = _enclosing_condition_label(source, node)
            fr.calls.append(
                CallSite(
                    caller_id=current_fn,
                    callee_hint=callee if callee else "unknown::call",
                    resolution=_call_resolution(callee) if callee else "unknown",
                    is_async=False,
                    line=line,
                    condition_label=cond,
                ),
            )
        for c in node.children:
            self._walk(c, source, file_key, fr, class_name=class_name, current_fn=current_fn)
