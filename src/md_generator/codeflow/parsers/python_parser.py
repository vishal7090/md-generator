from __future__ import annotations

import ast
from pathlib import Path

from md_generator.codeflow.graph.relations import REL_REFERENCES
from md_generator.codeflow.models.ir import (
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


def _sid(key: str, cls: str | None, name: str) -> str:
    if cls:
        return f"{key}::{cls}.{name}"
    return f"{key}::{name}"


def _collect_defined_functions(tree: ast.Module) -> set[tuple[str | None, str]]:
    found: set[tuple[str | None, str]] = set()

    def from_class(cls: ast.ClassDef) -> None:
        for n in cls.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.add((cls.name, n.name))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            from_class(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.add((None, node.name))
    return found


class PythonParser:
    language = "python"

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        root = project_root.resolve()
        key = _rel_key(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text, filename=str(path))
        fr = FileParseResult(path=path.resolve(), language=self.language)

        imports: dict[str, str] = {}
        self._gather_imports(tree, imports)
        defined = _collect_defined_functions(tree)

        visitor = _MethodVisitor(
            file_key=key,
            imports=imports,
            defined=defined,
            fr=fr,
            path=str(path.resolve()),
        )
        visitor.walk_module(tree)

        fr.entries.extend(self._detect_main_guard(tree, key, path))
        fr.entries.extend(self._detect_cli(tree, key, path))

        return fr

    def _gather_imports(self, tree: ast.AST, imports: dict[str, str]) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split(".")[0]] = alias.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    nm = alias.name
                    imports[alias.asname or nm] = f"{mod}.{nm}" if mod else nm

    def _is_main_guard(self, node: ast.If) -> bool:
        try:
            g = ast.unparse(node.test)
        except Exception:
            return False
        return g.replace(" ", "") in (
            '__name__=="__main__"',
            "__name__=='__main__'",
        )

    def _detect_main_guard(self, tree: ast.Module, key: str, path: Path) -> list[EntryRecord]:
        out: list[EntryRecord] = []
        for node in tree.body:
            if isinstance(node, ast.If) and self._is_main_guard(node):
                out.append(
                    EntryRecord(
                        symbol_id=_sid(key, None, "__main__"),
                        kind=EntryKind.MAIN,
                        label="Python __main__ guard",
                        file_path=str(path.resolve()),
                        line=node.lineno,
                    )
                )
                break
        return out

    def _detect_cli(self, tree: ast.Module, key: str, path: Path) -> list[EntryRecord]:
        hits: list[EntryRecord] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "ArgumentParser":
                    hits.append(
                        EntryRecord(
                            symbol_id=_sid(key, None, "cli"),
                            kind=EntryKind.CLI,
                            label="argparse CLI",
                            file_path=str(path.resolve()),
                            line=node.lineno,
                        )
                    )
                    break
        return hits


class _MethodVisitor:
    def __init__(
        self,
        *,
        file_key: str,
        imports: dict[str, str],
        defined: set[tuple[str | None, str]],
        fr: FileParseResult,
        path: str,
    ) -> None:
        self.file_key = file_key
        self.imports = imports
        self.defined = defined
        self.fr = fr
        self.path = path
        self.class_stack: list[str] = []
        self.branch_stack: list[str | None] = []
        self._refs_left = 40

    def walk_module(self, tree: ast.Module) -> None:
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self._visit_class(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_function(node, None)

    def _visit_class(self, cls: ast.ClassDef) -> None:
        self.class_stack.append(cls.name)
        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_function(node, cls.name)
            elif isinstance(node, ast.ClassDef):
                self._visit_class(node)
        self.class_stack.pop()

    def _visit_function(self, fn: ast.FunctionDef | ast.AsyncFunctionDef, outer_class: str | None) -> None:
        cls = outer_class if outer_class is not None else (self.class_stack[-1] if self.class_stack else None)
        name = fn.name
        caller = _sid(self.file_key, cls, name)
        if caller not in self.fr.symbol_ids:
            self.fr.symbol_ids.append(caller)

        self._refs_left = 40
        is_async = isinstance(fn, ast.AsyncFunctionDef)
        self._walk_body(fn.body, caller, is_async)

    def _walk_body(self, nodes: list[ast.stmt], caller: str, is_async_fn: bool) -> None:
        for st in nodes:
            self._walk_stmt(st, caller, is_async_fn)

    def _walk_stmt(self, st: ast.stmt, caller: str, is_async_fn: bool) -> None:
        if isinstance(st, ast.If):
            lbl = self._if_label(st)
            self.branch_stack.append(lbl)
            for sub in st.body:
                self._walk_stmt(sub, caller, is_async_fn)
            self.branch_stack.pop()
            self.branch_stack.append(f"else(L{st.lineno})")
            for sub in st.orelse:
                self._walk_stmt(sub, caller, is_async_fn)
            self.branch_stack.pop()
            return
        if isinstance(st, (ast.For, ast.While)):
            self.branch_stack.append(f"loop(L{st.lineno})")
            for sub in st.body:
                self._walk_stmt(sub, caller, is_async_fn)
            self.branch_stack.pop()
            return
        if isinstance(st, ast.Try):
            for sub in st.body:
                self._walk_stmt(sub, caller, is_async_fn)
            for h in st.handlers:
                self.branch_stack.append(f"except(L{h.lineno})")
                for sub in h.body:
                    self._walk_stmt(sub, caller, is_async_fn)
                self.branch_stack.pop()
            for sub in st.finalbody:
                self._walk_stmt(sub, caller, is_async_fn)
            return
        if isinstance(st, ast.With):
            for sub in st.body:
                self._walk_stmt(sub, caller, is_async_fn)
            return
        if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            value = getattr(st, "value", None)
            if isinstance(value, ast.expr):
                self._visit_expr(value, caller, is_async_fn)
            return
        if isinstance(st, ast.Expr):
            self._visit_expr(st.value, caller, is_async_fn)
            return
        if isinstance(st, ast.Return) and st.value:
            self._visit_expr(st.value, caller, is_async_fn)
            return
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cls = self.class_stack[-1] if self.class_stack else None
            self._visit_function(st, cls)
            return
        if isinstance(st, ast.ClassDef):
            self._visit_class(st)
            return

    def _emit_reference(self, caller: str, expr: ast.Attribute) -> None:
        if self._refs_left <= 0:
            return
        try:
            hint = ast.unparse(expr).replace(" ", "")[:220]
        except Exception:
            hint = f"attr.{expr.attr}"
        self.fr.structural_edges.append(
            StructuralEdge(
                source_id=caller,
                target_id=f"external::{hint}",
                relation=REL_REFERENCES,
                confidence=0.7,
                line=getattr(expr, "lineno", None),
            ),
        )
        self._refs_left -= 1

    def _visit_expr(self, expr: ast.expr, caller: str, is_async_fn: bool) -> None:
        if isinstance(expr, ast.Attribute):
            self._emit_reference(caller, expr)
        if isinstance(expr, ast.Call):
            self._visit_call(expr, caller, is_async_fn)
            for a in expr.args:
                self._visit_expr(a, caller, is_async_fn)
            for kw in expr.keywords:
                if kw.value:
                    self._visit_expr(kw.value, caller, is_async_fn)
            return
        if isinstance(expr, ast.Await):
            if isinstance(expr.value, ast.Call):
                self._visit_call(expr.value, caller, True)
            else:
                self._visit_expr(expr.value, caller, is_async_fn)
            return
        if isinstance(expr, ast.Lambda):
            self._visit_expr(expr.body, caller, is_async_fn)
            return
        for sub in ast.iter_child_nodes(expr):
            if isinstance(sub, ast.expr):
                self._visit_expr(sub, caller, is_async_fn)

    def _if_label(self, node: ast.If) -> str:
        try:
            t = ast.unparse(node.test)
            t = t.replace("\n", " ")
            if len(t) > 80:
                t = t[:77] + "..."
            return f"if({t})"
        except Exception:
            return f"if(L{node.lineno})"

    def _visit_call(self, node: ast.Call, caller: str, is_async_fn: bool) -> None:
        callee, res = self._resolve_callee(node.func)
        cond = self.branch_stack[-1] if self.branch_stack else None
        line = getattr(node, "lineno", 0) or 0
        self.fr.calls.append(
            CallSite(
                caller_id=caller,
                callee_hint=callee,
                resolution=res if res in ("static", "dynamic", "unknown") else "unknown",
                is_async=is_async_fn,
                line=line,
                condition_label=cond,
            )
        )

    def _resolve_callee(self, func: ast.expr) -> tuple[str, CallResolution]:
        if isinstance(func, ast.Name):
            hint = func.id
            cls = self.class_stack[-1] if self.class_stack else None
            if (cls, hint) in self.defined:
                return _sid(self.file_key, cls, hint), "static"
            if (None, hint) in self.defined:
                return _sid(self.file_key, None, hint), "static"
            return f"unknown::{hint}", "unknown"
        if isinstance(func, ast.Attribute):
            attr = func.attr
            base = func.value
            if isinstance(base, ast.Name) and base.id == "self" and self.class_stack:
                return _sid(self.file_key, self.class_stack[-1], attr), "static"
            try:
                return ast.unparse(func).replace(" ", ""), "dynamic"
            except Exception:
                return f"unknown::{attr}", "unknown"
        try:
            return ast.unparse(func), "dynamic"
        except Exception:
            return "unknown::expr", "unknown"
