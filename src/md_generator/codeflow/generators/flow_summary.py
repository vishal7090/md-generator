"""High-level flow narrative and method roles from a ``FlowSlice``."""

from __future__ import annotations

from collections import defaultdict

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice


def _edge_condition(ed: dict) -> str | None:
    c = ed.get("condition")
    if c:
        return str(c)
    labs = ed.get("labels") or []
    for lab in reversed(labs):
        if lab:
            return str(lab)
    return None


def _pretty_method(g: nx.DiGraph, nid: str) -> str:
    if nid not in g:
        tail = nid.split("::")[-1] if "::" in nid else nid
        if "." in tail:
            cls, meth = tail.rsplit(".", 1)
            return f"{cls}.{meth}()"
        return f"{tail}()"
    d = g.nodes[nid]
    cn = d.get("class_name")
    mn = d.get("method_name")
    if not mn:
        tail = nid.split("::")[-1] if "::" in nid else nid
        if "." in tail:
            cls, meth = tail.rsplit(".", 1)
            return f"{cls}.{meth}()"
        return f"{tail}()"
    if cn:
        return f"{cn}.{mn}()"
    return f"{mn}()"


def _class_method_from_id(g: nx.DiGraph, nid: str) -> tuple[str | None, str]:
    if nid in g:
        d = g.nodes[nid]
        return d.get("class_name"), d.get("method_name") or nid.split("::")[-1].split(".")[-1]
    tail = nid.split("::")[-1] if "::" in nid else nid
    if "." in tail:
        cls, meth = tail.rsplit(".", 1)
        return cls, meth
    return None, tail


def _build_adjacency(sl: FlowSlice) -> dict[str, list[tuple[str, dict]]]:
    adj: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    for u, v, ed in sl.edges:
        key = (u, v)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        adj[u].append((v, dict(ed)))
    return adj


def _partition_edges(
    outs: list[tuple[str, dict]],
) -> tuple[list[tuple[str, dict]], list[tuple[str, str, dict]]]:
    uncond: list[tuple[str, dict]] = []
    cond: list[tuple[str, str, dict]] = []
    for v, ed in outs:
        lbl = _edge_condition(ed)
        if lbl:
            cond.append((lbl, v, ed))
        else:
            uncond.append((v, ed))
    return uncond, cond


def _role_token(method_name: str, class_name: str | None) -> str | None:
    hay = f"{class_name or ''}.{method_name}".lower()
    for token, label in (
        ("controller", "controller layer"),
        ("service", "service layer"),
        ("repository", "repository / persistence"),
        ("repo", "repository / persistence"),
        ("handler", "handler"),
        ("consumer", "consumer"),
        ("producer", "producer"),
        ("listener", "event listener"),
    ):
        if token in hay:
            return label
    return None


def method_roles(
    sl: FlowSlice,
    g: nx.DiGraph,
    entry_id: str,
) -> dict[str, str]:
    """Map node id → short role phrase for Method Summary."""
    adj = _build_adjacency(sl)

    def out_degree_cond(u: str) -> int:
        _, cond = _partition_edges(adj.get(u, []))
        return len(cond)

    roles: dict[str, str] = {}
    for nid in sl.nodes:
        cls, meth = _class_method_from_id(g, nid)
        if nid == entry_id:
            roles[nid] = "start method"
            continue
        outs_n = adj.get(nid, [])
        if out_degree_cond(nid) >= 1:
            roles[nid] = "decision logic"
            continue
        tok = _role_token(meth, cls)
        if tok:
            roles[nid] = tok
            continue
        succ = [v for v, _ in outs_n]
        if not succ:
            roles[nid] = "leaf / terminal"
        else:
            roles[nid] = "processing method"
    return roles


def _async_suffix(ed: dict) -> str:
    return " [async]" if ed.get("async_") or ed.get("type") == "async" else ""


def format_flow_description(sl: FlowSlice, g: nx.DiGraph) -> list[str]:
    """Numbered flow with optional ``if`` / ``else`` nesting from edge conditions."""
    lines: list[str] = []
    adj = _build_adjacency(sl)
    entry = sl.entry_id
    if entry not in sl.nodes:
        lines.append("*Entry not in slice.*")
        return lines

    step_of: dict[str, int] = {}
    counter = [0]
    described: set[str] = set()

    def next_step(nid: str) -> int:
        if nid not in step_of:
            counter[0] += 1
            step_of[nid] = counter[0]
        return step_of[nid]

    def callee_line(indent: str, v: str, ed: dict) -> None:
        if v in described and v in step_of:
            lines.append(
                f"{indent}→ calls {_pretty_method(g, v)}{_async_suffix(ed)} (see step {step_of[v]})",
            )
        else:
            lines.append(f"{indent}→ calls {_pretty_method(g, v)}{_async_suffix(ed)}")

    def emit_conditional_chain(
        conds: list[tuple[str, str, dict]],
        unconds: list[tuple[str, dict]],
        indent: str,
    ) -> None:
        if not conds:
            return
        c0, v0, ed0 = conds[0]
        lines.append(f"{indent}→ if ({c0})")
        callee_line(f"{indent}   ", v0, ed0)
        if len(conds) == 1:
            if unconds:
                lines.append(f"{indent}→ else")
                for v, ed in unconds:
                    callee_line(f"{indent}   ", v, ed)
            return
        lines.append(f"{indent}→ else")
        inner = indent + "   "
        emit_conditional_chain(conds[1:], unconds, inner)

    def emit_outgoing_block(u: str, indent: str) -> None:
        outs = adj.get(u, [])
        if not outs:
            return
        unconds, conds = _partition_edges(outs)
        for v, ed in unconds:
            callee_line(indent, v, ed)
        if conds:
            emit_conditional_chain(conds, [], indent)

    def walk(u: str, stack: set[str]) -> None:
        if u in described:
            return
        if u in stack:
            lines.append("   → (cycle)")
            return
        stack = set(stack)
        stack.add(u)
        n = next_step(u)
        described.add(u)
        lines.append("")
        lines.append(f"{n}. {_pretty_method(g, u)}")
        if sl.truncated and u == entry:
            lines.append("")
            lines.append("*Truncated by depth limit.*")
        if sl.cycle_nodes and u in sl.cycle_nodes:
            lines.append("")
            lines.append(f"*Possible cycles or revisits near:* `{u}`")
        emit_outgoing_block(u, "")
        outs = adj.get(u, [])
        unconds, conds = _partition_edges(outs)
        raw_children = [v for v, _ in unconds] + [v for _, v, _ in conds]
        seen: set[str] = set()
        child_order: list[str] = []
        for v in sorted(raw_children):
            if v not in sl.nodes or v in seen:
                continue
            seen.add(v)
            child_order.append(v)
        for v in child_order:
            walk(v, stack)
        stack.discard(u)

    walk(entry, set())
    if lines and lines[0] == "":
        lines.pop(0)
    return lines


def format_method_summary_lines(sl: FlowSlice, g: nx.DiGraph, entry_id: str) -> list[str]:
    """``### Class`` sections with ``- method() → role`` bullets."""
    roles = method_roles(sl, g, entry_id)
    by_class: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for nid in sorted(sl.nodes):
        cls, meth = _class_method_from_id(g, nid)
        key = cls or "(file scope)"
        by_class[key].append((meth, roles.get(nid, "processing method")))
    lines: list[str] = []
    for cls in sorted(by_class.keys()):
        lines.append(f"### {cls}")
        for meth, role in sorted(by_class[cls], key=lambda x: x[0]):
            lines.append(f"- {meth}() → {role}")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def one_line_summary(sl: FlowSlice, g: nx.DiGraph, max_chars: int = 120) -> str:
    """First hop or two for overview table."""
    adj = _build_adjacency(sl)
    e = sl.entry_id
    outs = adj.get(e, [])
    if not outs:
        return _pretty_method(g, e)
    parts = [_pretty_method(g, e)]
    for v, ed in outs[:2]:
        parts.append(f"→ {_pretty_method(g, v)}")
    s = " ".join(parts)
    return s if len(s) <= max_chars else s[: max_chars - 3] + "..."
