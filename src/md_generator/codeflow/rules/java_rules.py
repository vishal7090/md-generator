"""Heuristic business rules from Java sources (annotations, throws) for codeflow slices."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.models.ir import BusinessRule
from md_generator.codeflow.parsers.python_parser import _rel_key


def _sid_java(key: str, cls: str, method: str) -> str:
    return f"{key}::{cls}.{method}"


_VALIDATION_EXCEPTIONS = frozenset(
    {
        "IllegalArgumentException",
        "IllegalStateException",
        "ValidationException",
        "ConstraintViolationException",
        "NullPointerException",
        "SecurityException",
        "BadRequestException",
        "UnprocessableEntityException",
    },
)

_RULE_ANNOTATIONS = frozenset(
    {
        "NotNull",
        "NonNull",
        "NotEmpty",
        "NotBlank",
        "Size",
        "Min",
        "Max",
        "Pattern",
        "Valid",
        "Validated",
        "Email",
        "Positive",
        "PositiveOrZero",
        "Negative",
        "NegativeOrZero",
        "DecimalMin",
        "DecimalMax",
        "Digits",
        "Future",
        "Past",
    },
)


def _ann_simple_name(ann: object) -> str:
    n = getattr(ann, "name", None) or str(ann)
    return str(n).split(".")[-1]


def _throw_exception_name(expr: object) -> str | None:
    if expr is None:
        return None
    if type(expr).__name__ != "ClassCreator":
        return None
    typ = getattr(expr, "type", None)
    if typ is None:
        return None
    nm = getattr(typ, "name", None)
    if not nm:
        return None
    return str(nm).split(".")[-1]


def _iter_java_subtree(root: object):
    import javalang.tree as jt

    mod = jt.__name__
    stack: list[object] = [root]
    while stack:
        n = stack.pop()
        yield n
        for name in getattr(n, "attrs", ()) or ():
            if name in ("position", "label", "documentation"):
                continue
            v = getattr(n, name, None)
            if isinstance(v, list):
                for x in reversed(v):
                    if x is not None and getattr(type(x), "__module__", "") == mod:
                        stack.append(x)
            elif v is not None and getattr(type(v), "__module__", "") == mod:
                stack.append(v)


def extract_java_method_rules(path: Path, project_root: Path, target_sids: set[str]) -> list[BusinessRule]:
    import javalang
    from javalang.tree import ClassCreator, MethodDeclaration, ThrowStatement

    rules: list[BusinessRule] = []
    key = _rel_key(path, project_root)
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = javalang.parse.parse(text)
    except Exception:
        return rules

    for t in tree.types or []:
        cls_name = getattr(t, "name", None)
        if not cls_name:
            continue
        for m in getattr(t, "methods", None) or []:
            if not isinstance(m, MethodDeclaration):
                continue
            sid = _sid_java(key, cls_name, m.name)
            if sid not in target_sids:
                continue
            fp = str(path.resolve())
            pos = getattr(m, "position", None)
            base_line = int(getattr(pos, "line", 0) or 0) if pos else 1

            for ann in getattr(m, "annotations", None) or []:
                nm = _ann_simple_name(ann)
                if nm in _RULE_ANNOTATIONS:
                    rules.append(
                        BusinessRule(
                            source="validation",
                            symbol_id=sid,
                            file_path=fp,
                            line=base_line,
                            title=f"Validation annotation `@{nm}`",
                            detail=f"Method `{m.name}`",
                            confidence="medium",
                        ),
                    )
            for p in getattr(m, "parameters", None) or []:
                for ann in getattr(p, "annotations", None) or []:
                    nm = _ann_simple_name(ann)
                    if nm in _RULE_ANNOTATIONS:
                        pln = int(getattr(getattr(p, "position", None), "line", 0) or 0) or base_line
                        rules.append(
                            BusinessRule(
                                source="validation",
                                symbol_id=sid,
                                file_path=fp,
                                line=pln,
                                title=f"Validation annotation `@{nm}`",
                                detail=f"Parameter `{getattr(p, 'name', '?')}`",
                                confidence="medium",
                            ),
                        )

            body = m.body
            roots: list = []
            if body is None:
                roots = []
            elif isinstance(body, list):
                roots = body
            else:
                roots = getattr(body, "statements", None) or []

            seen_throw: set[int] = set()
            for root_stmt in roots:
                for st in _iter_java_subtree(root_stmt):
                    if not isinstance(st, ThrowStatement):
                        continue
                    i = id(st)
                    if i in seen_throw:
                        continue
                    seen_throw.add(i)
                    exc = _throw_exception_name(st.expression)
                    if exc and exc in _VALIDATION_EXCEPTIONS:
                        ln = base_line
                        sp = getattr(st, "position", None)
                        if sp:
                            ln = int(getattr(sp, "line", 0) or 0) or ln
                        detail = "throw"
                        if isinstance(st.expression, ClassCreator):
                            detail = f"throw new {exc}(…)"
                        rules.append(
                            BusinessRule(
                                source="validation",
                                symbol_id=sid,
                                file_path=fp,
                                line=ln or 1,
                                title=f"Throw {exc}",
                                detail=detail,
                                confidence="high" if exc in ("IllegalArgumentException", "ValidationException") else "medium",
                            ),
                        )
    return rules
