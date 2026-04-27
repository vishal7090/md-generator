from __future__ import annotations

from pathlib import Path

import javalang.tree

from md_generator.codeflow.models.ir import CallSite, CallResolution, EntryKind, EntryRecord, FileParseResult


def _rel_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sid(key: str, cls: str, method: str) -> str:
    return f"{key}::{cls}.{method}"


def _iter_javalang_tree(node: object):
    """Depth-first iteration over javalang.tree nodes reachable from a statement/expression."""
    stack: list[object] = [node]
    seen: set[int] = set()
    while stack:
        n = stack.pop()
        i = id(n)
        if i in seen:
            continue
        seen.add(i)
        yield n
        attrs = getattr(n, "attrs", None)
        if not attrs:
            continue
        for name in attrs:
            val = getattr(n, name, None)
            if val is None:
                continue
            if isinstance(val, list):
                for x in val:
                    if x is not None and getattr(type(x), "__module__", "") == javalang.tree.__name__:
                        stack.append(x)
            elif getattr(type(val), "__module__", "") == javalang.tree.__name__:
                stack.append(val)


class JavaParser:
    language = "java"

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        import javalang
        from javalang.tree import MethodDeclaration, MethodInvocation

        root = project_root.resolve()
        key = _rel_key(path, root)
        text = path.read_text(encoding="utf-8", errors="replace")
        fr = FileParseResult(path=path.resolve(), language=self.language)

        try:
            tree = javalang.parse.parse(text)
        except Exception:
            return fr

        for t in tree.types or []:
            cls_name = getattr(t, "name", None)
            if not cls_name:
                continue
            for m in getattr(t, "methods", None) or []:
                if not isinstance(m, MethodDeclaration):
                    continue
                caller = _sid(key, cls_name, m.name)
                fr.symbol_ids.append(caller)
                body = m.body or []
                for node in body:
                    for sub in _iter_javalang_tree(node):
                        if isinstance(sub, MethodInvocation):
                            callee = self._format_invocation(sub)
                            pos = getattr(sub, "position", None)
                            line = int(getattr(pos, "line", 0) or 0) if pos else 0
                            fr.calls.append(
                                CallSite(
                                    caller_id=caller,
                                    callee_hint=callee,
                                    resolution=self._resolution_for_invocation(sub),
                                    is_async=False,
                                    line=line,
                                    condition_label=None,
                                )
                            )

                ann_text = " ".join(str(getattr(a, "name", a)) for a in (getattr(m, "annotations", None) or []))
                if "KafkaListener" in ann_text or "kafka" in ann_text.lower():
                    pos = getattr(m, "position", None)
                    line = int(getattr(pos, "line", 0) or 0) if pos else 0
                    fr.entries.append(
                        EntryRecord(
                            symbol_id=caller,
                            kind=EntryKind.KAFKA,
                            label="Kafka listener",
                            file_path=str(path.resolve()),
                            line=line,
                        )
                    )

        return fr

    def _format_invocation(self, expr: object) -> str:
        qual = getattr(expr, "qualifier", None) or ""
        member = getattr(expr, "member", "") or ""
        if qual:
            return f"{qual}.{member}"
        return member or "unknown"

    def _resolution_for_invocation(self, expr: object) -> CallResolution:
        qual = getattr(expr, "qualifier", None) or ""
        return "static" if qual else "dynamic"
