"""JavaScript / TypeScript / TSX parsing via Tree-sitter."""

from __future__ import annotations

import logging
from pathlib import Path

from tree_sitter import Language, Node, Parser

from md_generator.codeflow.models.ir import CallSite, CallResolution, FileParseResult

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
            fr.calls.append(
                CallSite(
                    caller_id=current_fn,
                    callee_hint=callee if callee else "unknown::call",
                    resolution=_call_resolution(callee) if callee else "unknown",
                    is_async=False,
                    line=line,
                    condition_label=None,
                )
            )
        for c in node.children:
            self._walk(c, source, file_key, fr, class_name=class_name, current_fn=current_fn)
