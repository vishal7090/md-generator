"""C/C++ parsing: prefer libclang; fall back to Tree-sitter C/C++ when clang is unavailable."""

from __future__ import annotations

import logging
from pathlib import Path

from md_generator.codeflow.models.ir import BranchPoint, CallSite, FileParseResult

logger = logging.getLogger(__name__)


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sid(key: str, name: str) -> str:
    return f"{key}::{name}"


def _trim_cpp(source: bytes, s: str, max_len: int = 120) -> str:
    del source
    s = " ".join(s.split())
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _enclosing_condition_cpp(source: bytes, call: object) -> str | None:
    cur = getattr(call, "parent", None)
    while cur is not None:
        t = cur.type
        if t == "if_statement":
            for ch in cur.children:
                if ch.type == "condition_clause":
                    return _trim_cpp(source, source[ch.start_byte : ch.end_byte].decode("utf-8", errors="replace"))
            return "if (…)"
        if t == "while_statement":
            for ch in cur.children:
                if ch.type == "condition_clause":
                    return _trim_cpp(source, source[ch.start_byte : ch.end_byte].decode("utf-8", errors="replace"))
            return "while (…)"
        if t == "for_statement":
            cond = cur.child_by_field_name("condition") if hasattr(cur, "child_by_field_name") else None
            if cond:
                return _trim_cpp(source, source[cond.start_byte : cond.end_byte].decode("utf-8", errors="replace"))
            return "for (…)"
        if t == "conditional_expression":
            cond = cur.child_by_field_name("condition")
            if cond:
                return _trim_cpp(source, source[cond.start_byte : cond.end_byte].decode("utf-8", errors="replace"))
            return "… ? … : …"
        if t == "case_statement":
            bits: list[str] = []
            for c in cur.children:
                if c.type == ":":
                    break
                if c.type == "default":
                    return "default:"
                if c.type != "case":
                    bits.append(source[c.start_byte : c.end_byte].decode("utf-8", errors="replace").strip())
            return _trim_cpp(source, "case " + " ".join(bits)) if bits else "case …"
        if t == "function_definition":
            break
        cur = getattr(cur, "parent", None)
    return None


class CppParser:
    language = "cpp"

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        fr = FileParseResult(path=path.resolve(), language=self.language)
        key = _rel_key(path, project_root)
        if self._parse_clang(path, key, fr):
            return fr
        if self._parse_treesitter_cpp(path, key, fr):
            return fr
        return fr

    def _parse_clang(self, path: Path, key: str, fr: FileParseResult) -> bool:
        try:
            import clang.cindex as ci  # type: ignore[import-not-found]
        except Exception as e:
            logger.debug("clang not available: %s", e)
            return False
        try:
            index = ci.Index.create()
            if path.suffix.lower() == ".c":
                args = ["-x", "c"]
            else:
                args = ["-x", "c++"]
            tu = index.parse(str(path), args=args)
        except Exception as e:
            logger.debug("clang parse failed %s: %s", path, e)
            return False

        def collect_calls(body: object, caller_id: str) -> None:
            stack = list(body.get_children())
            while stack:
                cur = stack.pop()
                if cur.kind == ci.CursorKind.CALL_EXPR:
                    callee = cur.spelling or cur.displayname or "unknown"
                    line = int(cur.location.line) if cur.location and cur.location.file else 0
                    fr.calls.append(
                        CallSite(
                            caller_id=caller_id,
                            callee_hint=callee,
                            resolution="dynamic",
                            is_async=False,
                            line=line,
                            condition_label=None,
                        )
                    )
                stack.extend(cur.get_children())

        def visit(cur: object) -> None:
            if cur.kind == ci.CursorKind.FUNCTION_DECL and cur.is_definition():
                name = cur.spelling or "<anonymous>"
                fid = _sid(key, name)
                if fid not in fr.symbol_ids:
                    fr.symbol_ids.append(fid)
                for ch in cur.get_children():
                    if ch.kind == ci.CursorKind.COMPOUND_STMT:
                        collect_calls(ch, fid)
                        break
                return
            for ch in cur.get_children():
                visit(ch)

        try:
            visit(tu.cursor)
        except Exception as e:
            logger.debug("clang walk failed %s: %s", path, e)
            return False
        return bool(fr.symbol_ids or fr.calls)

    def _parse_treesitter_cpp(self, path: Path, key: str, fr: FileParseResult) -> bool:
        try:
            import tree_sitter_cpp as tscpp
            from tree_sitter import Language, Parser
        except Exception as e:
            logger.debug("tree-sitter-cpp not available: %s", e)
            return False
        try:
            lang = Language(tscpp.language())
            parser = Parser(lang)
            source = path.read_bytes()
            tree = parser.parse(source)
        except Exception as e:
            logger.debug("tree-sitter cpp parse failed %s: %s", path, e)
            return False

        def text(node: object) -> str:
            return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        def walk(node: object, class_name: str | None, cur_fn: str | None) -> None:
            t = node.type
            if t == "class_specifier":
                nm_node = node.child_by_field_name("name")
                nm = text(nm_node).strip() if nm_node else None
                body = node.child_by_field_name("body")
                if body:
                    for ch in body.children:
                        walk(ch, nm, cur_fn)
                return
            if t == "function_definition":
                decl = node.child_by_field_name("declarator")
                fn_name = "<fn>"
                if decl:
                    raw = text(decl).strip()
                    if "(" in raw:
                        head = raw.split("(", 1)[0].strip()
                        fn_name = head.split()[-1] if head else fn_name
                fid = _sid(key, f"{class_name}.{fn_name}" if class_name else fn_name)
                if fid not in fr.symbol_ids:
                    fr.symbol_ids.append(fid)
                body = node.child_by_field_name("body")
                if body:
                    for ch in body.children:
                        walk(ch, class_name, fid)
                return
            if t == "if_statement" and cur_fn:
                lab = "if (…)"
                for ch in node.children:
                    if ch.type == "condition_clause":
                        lab = _trim_cpp(source, text(ch))
                        break
                fr.branches.append(
                    BranchPoint(caller_id=cur_fn, kind="if", label=lab, line=node.start_point[0] + 1),
                )
            if t == "switch_statement" and cur_fn:
                for ch in node.children:
                    if ch.type != "compound_statement":
                        continue
                    for stmt in ch.children:
                        if stmt.type != "case_statement":
                            continue
                        bits: list[str] = []
                        for x in stmt.children:
                            if x.type == ":":
                                break
                            if x.type == "default":
                                bits = ["default"]
                                break
                            if x.type != "case":
                                bits.append(text(x).strip())
                        lab = _trim_cpp(source, "case " + " ".join(bits)) if bits else "case …"
                        fr.branches.append(
                            BranchPoint(
                                caller_id=cur_fn,
                                kind="switch",
                                label=lab,
                                line=stmt.start_point[0] + 1,
                            ),
                        )
            if t == "call_expression" and cur_fn:
                fn = node.child_by_field_name("function")
                callee = text(fn).strip() if fn else "unknown"
                cond = _enclosing_condition_cpp(source, node)
                fr.calls.append(
                    CallSite(
                        caller_id=cur_fn,
                        callee_hint=callee or "unknown::call",
                        resolution="dynamic",
                        is_async=False,
                        line=node.start_point[0] + 1,
                        condition_label=cond,
                    ),
                )
            for c in node.children:
                walk(c, class_name, cur_fn)

        walk(tree.root_node, None, None)
        return bool(fr.symbol_ids or fr.calls)
