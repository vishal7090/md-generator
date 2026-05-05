"""JSON IR (irVersion 1) from Go/PHP dumps → ``IRStmt`` / ``IRMethod``."""

from __future__ import annotations

from typing import Any

from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt

_VALID_KINDS = frozenset(
    {"IF", "LOOP", "SWITCH", "TRY", "CALL", "RETURN", "BREAK", "CONTINUE", "STATEMENT"},
)


def _stmt_from_dict(obj: dict[str, Any]) -> IRStmt:
    kind_raw = str(obj.get("kind") or "STATEMENT").upper()
    kind = kind_raw if kind_raw in _VALID_KINDS else "STATEMENT"
    cond = obj.get("condition")
    condition = str(cond).strip() if cond is not None and str(cond).strip() else None
    body_raw = obj.get("body")
    body = tuple(_stmt_from_dict(x) for x in body_raw if isinstance(x, dict)) if isinstance(body_raw, list) else ()
    else_raw = obj.get("else_body")
    else_body = tuple(_stmt_from_dict(x) for x in else_raw if isinstance(x, dict)) if isinstance(else_raw, list) else ()
    cases: list[tuple[str, tuple[IRStmt, ...]]] = []
    cases_raw = obj.get("cases")
    if isinstance(cases_raw, list):
        for c in cases_raw:
            if not isinstance(c, dict):
                continue
            lab = str(c.get("label") or "case")
            br = c.get("body")
            stmts = tuple(_stmt_from_dict(x) for x in br if isinstance(x, dict)) if isinstance(br, list) else ()
            cases.append((lab, stmts))
    target = obj.get("target")
    target_s = str(target).strip() if target is not None else None
    label = obj.get("label")
    label_s = str(label).strip() if label is not None else None
    line_raw = obj.get("line")
    line_i: int | None
    if isinstance(line_raw, int) and not isinstance(line_raw, bool):
        line_i = line_raw
    elif isinstance(line_raw, str) and line_raw.isdigit():
        line_i = int(line_raw)
    else:
        line_i = None
    return IRStmt(
        kind=kind,  # type: ignore[arg-type]
        condition=condition,
        body=body,
        else_body=else_body,
        cases=tuple(cases),
        target=target_s,
        label=label_s,
        line=line_i,
    )


def ir_methods_from_dump_doc(data: dict[str, Any], *, file_path: str, language: str) -> list[IRMethod]:
    """Build ``IRMethod`` list from a codeflow_*_dump top-level JSON object."""
    funcs = data.get("funcs")
    if not isinstance(funcs, list):
        return []
    out: list[IRMethod] = []
    for fn in funcs:
        if not isinstance(fn, dict):
            continue
        fid = str(fn.get("id") or "").strip()
        if not fid:
            continue
        name = fid.split("::")[-1] if "::" in fid else fid
        if "." in name:
            name = name.rsplit(".", 1)[-1]
        body_raw = fn.get("body")
        body = tuple(_stmt_from_dict(x) for x in body_raw if isinstance(x, dict)) if isinstance(body_raw, list) else ()
        out.append(IRMethod(symbol_id=fid, name=name, file_path=file_path, language=language, body=body))
    return out
