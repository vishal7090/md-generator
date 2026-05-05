"""Heuristic C/C++ validation rules (throw, assert) via tree-sitter when available."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.models.ir import BusinessRule
from md_generator.codeflow.parsers.python_parser import _rel_key


def _sid_cpp(key: str, name: str) -> str:
    return f"{key}::{name}"


def extract_cpp_method_rules(path: Path, project_root: Path, target_sids: set[str]) -> list[BusinessRule]:
    try:
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser
    except Exception:
        return []

    key = _rel_key(path, project_root)
    source = path.read_bytes()
    try:
        lang = Language(tscpp.language())
        parser = Parser(lang)
        tree = parser.parse(source)
    except Exception:
        return []

    rules: list[BusinessRule] = []
    fp = str(path.resolve())

    def text(node: object) -> str:
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def trim(s: str, n: int = 120) -> str:
        s = " ".join(s.split())
        return s if len(s) <= n else s[: n - 1] + "…"

    def fn_id_for_def(node: object, class_name: str | None) -> str | None:
        t = node.type
        if t != "function_definition":
            return None
        decl = node.child_by_field_name("declarator")
        fn_name = "<fn>"
        if decl:
            raw = text(decl).strip()
            if "(" in raw:
                head = raw.split("(", 1)[0].strip()
                fn_name = head.split()[-1] if head else fn_name
        return _sid_cpp(key, f"{class_name}.{fn_name}" if class_name else fn_name)

    stack: list[str | None] = []
    cls_stack: list[str | None] = [None]

    def visit(node: object) -> None:
        t = node.type
        if t == "class_specifier":
            nm_node = node.child_by_field_name("name")
            nm = text(nm_node).strip() if nm_node else None
            cls_stack.append(nm)
            for c in node.children:
                visit(c)
            cls_stack.pop()
            return
        if t == "function_definition":
            fid = fn_id_for_def(node, cls_stack[-1])
            if fid and fid in target_sids:
                stack.append(fid)
            body = node.child_by_field_name("body")
            if body:
                for c in body.children:
                    visit(c)
            if fid and fid in target_sids:
                stack.pop()
            return
        if t == "throw_statement" and stack and stack[-1]:
            parts = [text(c) for c in node.children if c.type not in ("throw", ";", "{")]
            det = trim("".join(parts)) if parts else "throw"
            rules.append(
                BusinessRule(
                    source="validation",
                    symbol_id=stack[-1],
                    file_path=fp,
                    line=node.start_point[0] + 1,
                    title="Throw",
                    detail=det,
                    confidence="medium",
                ),
            )
        if t == "call_expression" and stack and stack[-1]:
            fn = node.child_by_field_name("function")
            callee = text(fn).strip() if fn else ""
            if callee in ("assert", "static_assert"):
                args = node.child_by_field_name("arguments")
                det = trim(text(args)) if args else callee
                rules.append(
                    BusinessRule(
                        source="validation",
                        symbol_id=stack[-1],
                        file_path=fp,
                        line=node.start_point[0] + 1,
                        title=f"`{callee}`",
                        detail=det,
                        confidence="low",
                    ),
                )
        for c in node.children:
            visit(c)

    visit(tree.root_node)
    return rules
