"""Optional inlining of callee CFGs at CALL nodes (IR/CFG only; bounded recursion)."""

from __future__ import annotations

from md_generator.codeflow.graph.cfg_copy import clone_cfg_with_prefix, copy_cfg
from md_generator.codeflow.graph.cfg_model import CFG, CFGEdge, CFGNode
from md_generator.codeflow.graph.path_enumerator import find_cfg_end_id, find_cfg_start_id


def _symbol_tail(sid: str) -> str:
    return sid.split("::", 1)[-1] if "::" in sid else sid


def _call_label_matches_symbol(call_label: str, symbol_id: str) -> bool:
    lab = (call_label or "").strip()
    if not lab:
        return False
    tail = _symbol_tail(symbol_id)
    if tail == lab:
        return True
    if "." in tail and tail.rsplit(".", 1)[-1] == lab:
        return True
    if "." in lab and (tail == lab or tail.endswith("." + lab) or tail.endswith("::" + lab)):
        return True
    return False


def _resolve_callee_symbol_id(call_label: str, method_cfgs: dict[str, CFG], call_file_path: str) -> str | None:
    """Map CALL label to a ``method_cfgs`` key; prefer symbols whose id prefix matches the call's file."""
    lab = (call_label or "").strip()
    if not lab or not method_cfgs:
        return None

    def file_hint(sid: str) -> bool:
        prefix = sid.split("::", 1)[0] if "::" in sid else sid
        fp = (call_file_path or "").replace("\\", "/")
        pnorm = prefix.replace("\\", "/")
        return pnorm in fp or fp.endswith(pnorm) or pnorm.endswith(fp.split("/")[-1])

    scored: list[tuple[int, str]] = []
    for sid in method_cfgs:
        if not _call_label_matches_symbol(lab, sid):
            continue
        score = 0
        if file_hint(sid):
            score += 2
        if _symbol_tail(sid) == lab:
            score += 1
        scored.append((score, sid))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], len(t[1]), t[1]))
    return scored[0][1]


def _try_inline_call(
    work: CFG,
    method_cfgs: dict[str, CFG],
    call_id: str,
    depth: int,
    stack: list[str],
    max_call_depth: int,
    clone_serial: list[int],
) -> None:
    cn = work.nodes.get(call_id)
    if cn is None or cn.kind != "CALL":
        return

    callee_sid = _resolve_callee_symbol_id(cn.label, method_cfgs, cn.file_path)
    if not callee_sid or callee_sid not in method_cfgs:
        return

    if callee_sid in stack:
        work.nodes[call_id] = CFGNode(
            id=cn.id,
            kind=cn.kind,
            label=(cn.label or "call") + " (recursive)",
            method_name=cn.method_name,
            file_path=cn.file_path,
            line=cn.line,
        )
        return

    if depth >= max_call_depth:
        work.nodes[call_id] = CFGNode(
            id=cn.id,
            kind=cn.kind,
            label=(cn.label or "call") + " (max-depth)",
            method_name=cn.method_name,
            file_path=cn.file_path,
            line=cn.line,
        )
        return

    callee_src = method_cfgs[callee_sid]
    c_start = find_cfg_start_id(callee_src)
    c_end = find_cfg_end_id(callee_src)
    if not c_start or not c_end:
        return

    clone_serial[0] += 1
    prefix = f"inl{clone_serial[0]}_"
    clone, id_map = clone_cfg_with_prefix(callee_src, prefix)
    new_start = id_map[c_start]
    new_end = id_map[c_end]
    clone_ids = list(clone.nodes.keys())

    preds = [e for e in work.edges if e.target == call_id]
    succs = [e for e in work.edges if e.source == call_id]
    work.edges = [e for e in work.edges if e.source != call_id and e.target != call_id]
    del work.nodes[call_id]

    for nid, node in clone.nodes.items():
        work.nodes[nid] = node
    for e in clone.edges:
        work.edges.append(CFGEdge(e.source, e.target, e.label))

    for e in preds:
        work.edges.append(CFGEdge(e.source, new_start, e.label))
    for e in succs:
        work.edges.append(CFGEdge(new_end, e.target, e.label))

    new_stack = stack + [callee_sid]
    for nid in clone_ids:
        nn = work.nodes.get(nid)
        if nn is not None and nn.kind == "CALL":
            _try_inline_call(work, method_cfgs, nid, depth + 1, new_stack, max_call_depth, clone_serial)


def expand_cfg_calls(
    cfg: CFG,
    method_cfgs: dict[str, CFG],
    *,
    max_call_depth: int = 3,
    inline_calls: bool = False,
) -> CFG:
    """Return a CFG copy with CALL nodes inlined up to ``max_call_depth`` (recursion-safe)."""
    if not inline_calls or not method_cfgs:
        return copy_cfg(cfg)

    work = copy_cfg(cfg)
    serial = [0]
    for call_id in list(work.nodes.keys()):
        node = work.nodes.get(call_id)
        if node is not None and node.kind == "CALL":
            _try_inline_call(work, method_cfgs, call_id, 0, [], max(0, max_call_depth), serial)
    return work


def build_method_cfg_index(parse_results: list, max_nodes: int) -> dict[str, CFG]:
    """Build ``symbol_id -> CFG`` for every ``IRMethod`` on parse results."""
    from md_generator.codeflow.graph.cfg_builder import build_cfg_from_ir
    from md_generator.codeflow.models.ir_cfg import IRMethod

    out: dict[str, CFG] = {}
    for pr in parse_results:
        for ir in getattr(pr, "ir_methods", ()) or ():
            if isinstance(ir, IRMethod):
                out[ir.symbol_id] = build_cfg_from_ir(ir, max_nodes=max_nodes)
    return out
