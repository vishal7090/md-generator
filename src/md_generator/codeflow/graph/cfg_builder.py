"""Build CFG from normalized IR only (no AST / javalang / tree-sitter imports)."""

from __future__ import annotations

from md_generator.codeflow.graph.cfg_model import CFG, CFGEdge
from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt


def build_cfg_from_ir(ir: IRMethod, *, max_nodes: int = 500) -> CFG:
    """Construct a static CFG sketch from ``IRMethod.body``."""
    cfg = CFG()
    used = 0
    start = cfg.add_node(
        prefix="N",
        kind="START",
        label="start",
        method_name=ir.name,
        file_path=ir.file_path,
        line=None,
    )
    used += 1
    exits, used = _emit_stmts(cfg, ir.body, [start], ir, max_nodes, used)
    end = cfg.add_node(
        prefix="N",
        kind="END",
        label="end",
        method_name=ir.name,
        file_path=ir.file_path,
        line=None,
    )
    used += 1
    for x in exits:
        cfg.add_edge(x, end)
    return cfg


def _emit_stmts(
    cfg: CFG,
    stmts: tuple[IRStmt, ...],
    preds: list[str],
    ir: IRMethod,
    max_nodes: int,
    used: int,
) -> tuple[list[str], int]:
    if not stmts:
        return preds, used
    cur_preds = preds
    for st in stmts:
        if used >= max_nodes:
            stub = cfg.add_node(
                prefix="N",
                kind="TRUNC",
                label="truncated",
                method_name=ir.name,
                file_path=ir.file_path,
                line=st.line,
            )
            used += 1
            for p in cur_preds:
                cfg.add_edge(p, stub)
            return [stub], used
        cur_preds, used = _emit_stmt(cfg, st, cur_preds, ir, max_nodes, used)
    return cur_preds, used


def _emit_stmt(
    cfg: CFG,
    st: IRStmt,
    preds: list[str],
    ir: IRMethod,
    max_nodes: int,
    used: int,
) -> tuple[list[str], int]:
    k = st.kind
    if k == "CALL":
        nid = cfg.add_node(
            prefix="N",
            kind="CALL",
            label=st.target or "call",
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        for p in preds:
            cfg.add_edge(p, nid)
        return [nid], used
    if k == "RETURN":
        nid = cfg.add_node(
            prefix="N",
            kind="RETURN",
            label=st.label or "return",
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        for p in preds:
            cfg.add_edge(p, nid)
        return [nid], used
    if k == "STATEMENT" and st.body:
        cur = preds
        for sub in st.body:
            cur, used = _emit_stmt(cfg, sub, cur, ir, max_nodes, used)
        return cur, used
    if k == "STATEMENT":
        nid = cfg.add_node(
            prefix="N",
            kind="STMT",
            label=(st.label or "stmt")[:120],
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        for p in preds:
            cfg.add_edge(p, nid)
        return [nid], used
    if k == "LOOP":
        hdr = cfg.add_node(
            prefix="L",
            kind="LOOP_HDR",
            label=st.condition or "loop",
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        for p in preds:
            cfg.add_edge(p, hdr)
        body_exits, used = _emit_stmts(cfg, st.body, [hdr], ir, max_nodes, used)
        for b in body_exits:
            cfg.add_edge(b, hdr, label="repeat")
        after = cfg.add_node(
            prefix="N",
            kind="LOOP_EXIT",
            label="after_loop",
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        cfg.add_edge(hdr, after, label="exit")
        return [after], used
    if k == "IF":
        return _emit_if(cfg, st, preds, ir, max_nodes, used)
    if k == "TRY":
        return _emit_try(cfg, st, preds, ir, max_nodes, used)
    if k == "SWITCH":
        return _emit_switch(cfg, st, preds, ir, max_nodes, used)

    nid = cfg.add_node(
        prefix="N",
        kind="STMT",
        label=st.kind,
        method_name=ir.name,
        file_path=ir.file_path,
        line=st.line,
    )
    used += 1
    for p in preds:
        cfg.add_edge(p, nid)
    return [nid], used


def _emit_if(
    cfg: CFG,
    st: IRStmt,
    preds: list[str],
    ir: IRMethod,
    max_nodes: int,
    used: int,
) -> tuple[list[str], int]:
    cond = cfg.add_node(
        prefix="I",
        kind="IF",
        label=st.condition or "if",
        method_name=ir.name,
        file_path=ir.file_path,
        line=st.line,
    )
    used += 1
    for p in preds:
        cfg.add_edge(p, cond)
    merge = cfg.add_node(
        prefix="M",
        kind="MERGE",
        label="after_if",
        method_name=ir.name,
        file_path=ir.file_path,
        line=st.line,
    )
    used += 1
    then_entry = cfg.add_node(
        prefix="T",
        kind="THEN",
        label="then",
        method_name=ir.name,
        file_path=ir.file_path,
        line=st.line,
    )
    used += 1
    cfg.add_edge(cond, then_entry, label="then")
    then_exits, used = _emit_stmts(cfg, st.body, [then_entry], ir, max_nodes, used)
    for t in then_exits:
        cfg.add_edge(t, merge)
    if st.else_body:
        else_entry = cfg.add_node(
            prefix="E",
            kind="ELSE",
            label="else",
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        cfg.add_edge(cond, else_entry, label="else")
        else_exits, used = _emit_stmts(cfg, st.else_body, [else_entry], ir, max_nodes, used)
        for e in else_exits:
            cfg.add_edge(e, merge)
    else:
        cfg.add_edge(cond, merge, label="no_else")
    return [merge], used


def _emit_try(
    cfg: CFG,
    st: IRStmt,
    preds: list[str],
    ir: IRMethod,
    max_nodes: int,
    used: int,
) -> tuple[list[str], int]:
    """Approximate try/catch/finally as a linear chain (documentation CFG only)."""
    try_n = cfg.add_node(
        prefix="T",
        kind="TRY",
        label="try",
        method_name=ir.name,
        file_path=ir.file_path,
        line=st.line,
    )
    used += 1
    for p in preds:
        cfg.add_edge(p, try_n)
    exits, used = _emit_stmts(cfg, st.body, [try_n], ir, max_nodes, used)
    cur = exits
    for c_label, c_body in st.cases:
        h = cfg.add_node(
            prefix="C",
            kind="CATCH",
            label=c_label[:80],
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        for x in cur:
            cfg.add_edge(x, h)
        cur, used = _emit_stmts(cfg, c_body, [h], ir, max_nodes, used)
    if st.else_body:
        fin = cfg.add_node(
            prefix="F",
            kind="FINALLY",
            label="finally",
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        for x in cur:
            cfg.add_edge(x, fin)
        cur, used = _emit_stmts(cfg, st.else_body, [fin], ir, max_nodes, used)
    return cur, used


def _emit_switch(
    cfg: CFG,
    st: IRStmt,
    preds: list[str],
    ir: IRMethod,
    max_nodes: int,
    used: int,
) -> tuple[list[str], int]:
    sw = cfg.add_node(
        prefix="S",
        kind="SWITCH",
        label=st.condition or "switch",
        method_name=ir.name,
        file_path=ir.file_path,
        line=st.line,
    )
    used += 1
    for p in preds:
        cfg.add_edge(p, sw)
    merge = cfg.add_node(
        prefix="M",
        kind="MERGE",
        label="after_switch",
        method_name=ir.name,
        file_path=ir.file_path,
        line=st.line,
    )
    used += 1
    if not st.cases:
        cfg.add_edge(sw, merge, label="switch")
        return [merge], used
    for case_label, case_body in st.cases:
        case_n = cfg.add_node(
            prefix="K",
            kind="CASE",
            label=case_label[:80],
            method_name=ir.name,
            file_path=ir.file_path,
            line=st.line,
        )
        used += 1
        cfg.add_edge(sw, case_n, label=case_label[:40])
        ex, used = _emit_stmts(cfg, case_body, [case_n], ir, max_nodes, used)
        for x in ex:
            cfg.add_edge(x, merge)
    return [merge], used


def cfg_to_serializable(cfg: CFG) -> dict:
    return {
        "nodes": [
            {
                "id": n.id,
                "kind": n.kind,
                "label": n.label,
                "method_name": n.method_name,
                "file_path": n.file_path,
                "line": n.line,
            }
            for n in cfg.nodes.values()
        ],
        "edges": [{"source": e.source, "target": e.target, "label": e.label} for e in cfg.edges],
    }


def cfg_edges_for_mermaid(cfg: CFG) -> list[CFGEdge]:
    return list(cfg.edges)
