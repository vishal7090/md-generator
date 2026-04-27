from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from md_generator.codeflow.models.ir import CallSite, FileParseResult


def _edge_unknown_call(call: CallSite, callee_id: str) -> bool:
    """True when the callee is not a confidently resolved static target (dynamic, unknown, proxy-style)."""
    if call.resolution in ("unknown", "dynamic"):
        return True
    if str(callee_id).startswith("unknown::"):
        return True
    return False


def _edge_recursive(caller_id: str, callee_id: str) -> bool:
    """True for direct self-calls (same symbol id as caller and callee)."""
    return caller_id == callee_id


@dataclass(slots=True)
class GraphBuildResult:
    graph: nx.DiGraph
    project_root: Path


def build_graph(parse_results: list[FileParseResult], project_root: Path) -> GraphBuildResult:
    """Merge file-level parse results into one DiGraph with node/edge attributes."""
    g = nx.DiGraph()
    root = project_root.resolve()

    for fr in parse_results:
        rel_file = _safe_rel(fr.path, root)
        for sid in fr.symbol_ids:
            if not g.has_node(sid):
                g.add_node(
                    sid,
                    id=sid,
                    type="method",
                    class_name=_class_from_symbol_id(sid),
                    method_name=_method_from_symbol_id(sid),
                    file_path=rel_file,
                    language=fr.language,
                )
            else:
                g.nodes[sid]["language"] = fr.language

        for e in fr.entries:
            fp = _safe_rel(Path(e.file_path), root) if e.file_path else rel_file
            if g.has_node(e.symbol_id):
                g.nodes[e.symbol_id]["entry_kind"] = e.kind.value
                g.nodes[e.symbol_id]["entry_label"] = e.label
                g.nodes[e.symbol_id]["type"] = "entry"
                if fp:
                    g.nodes[e.symbol_id]["file_path"] = fp
            else:
                g.add_node(
                    e.symbol_id,
                    id=e.symbol_id,
                    type="entry",
                    class_name=_class_from_symbol_id(e.symbol_id),
                    method_name=_method_from_symbol_id(e.symbol_id),
                    file_path=fp,
                    language=fr.language,
                    entry_kind=e.kind.value,
                    entry_label=e.label,
                )

        for call in fr.calls:
            callee_id = call.callee_hint
            if not g.has_node(callee_id):
                unresolved = call.resolution == "unknown" or callee_id.startswith("unknown::")
                g.add_node(
                    callee_id,
                    id=callee_id,
                    type="unknown" if unresolved else "method",
                    class_name=_class_from_unknown_id(callee_id),
                    method_name=_method_tail(callee_id),
                    file_path="",
                    language=fr.language,
                    unresolved=unresolved,
                )

            if not g.has_node(call.caller_id):
                g.add_node(
                    call.caller_id,
                    id=call.caller_id,
                    type="method",
                    class_name=_class_from_symbol_id(call.caller_id),
                    method_name=_method_from_symbol_id(call.caller_id),
                    file_path=rel_file,
                    language=fr.language,
                )

            edge_type = "async" if call.is_async else "sync"
            cond = call.condition_label
            unknown_call = _edge_unknown_call(call, callee_id)
            recursive = _edge_recursive(call.caller_id, callee_id)
            if g.has_edge(call.caller_id, callee_id):
                labs = list(g.edges[call.caller_id, callee_id].get("labels") or [])
                if cond and cond not in labs:
                    labs.append(cond)
                g.edges[call.caller_id, callee_id]["labels"] = labs
                if cond:
                    g.edges[call.caller_id, callee_id]["condition"] = cond
                ed = g.edges[call.caller_id, callee_id]
                ed["unknown_call"] = bool(ed.get("unknown_call")) or unknown_call
                ed["recursive"] = bool(ed.get("recursive")) or recursive
            else:
                g.add_edge(
                    call.caller_id,
                    callee_id,
                    type=edge_type,
                    resolution=call.resolution,
                    condition=cond,
                    labels=[cond] if cond else [],
                    async_=call.is_async,
                    unknown_call=unknown_call,
                    recursive=recursive,
                )

    return GraphBuildResult(graph=g, project_root=root)


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _class_from_symbol_id(sid: str) -> str | None:
    if "::" not in sid:
        return None
    tail = sid.split("::", 1)[1]
    if "." in tail:
        return tail.rsplit(".", 1)[0]
    return None


def _method_from_symbol_id(sid: str) -> str:
    if "::" not in sid:
        return sid
    tail = sid.split("::", 1)[1]
    if "." in tail:
        return tail.rsplit(".", 1)[1]
    return tail


def _class_from_unknown_id(cid: str) -> str | None:
    if cid.startswith("unknown::"):
        return None
    tail = cid.split("::")[-1] if "::" in cid else cid
    if "." in tail:
        return tail.rsplit(".", 1)[0]
    return None


def _method_tail(cid: str) -> str:
    tail = cid.split("::")[-1] if "::" in cid else cid
    if "." in tail:
        return tail.rsplit(".", 1)[1]
    return tail


def graph_to_serializable(g: nx.DiGraph) -> dict:
    nodes = []
    for n, attr in g.nodes(data=True):
        nodes.append({"id": n, **{k: v for k, v in attr.items() if k != "id"}})
    edges = []
    for u, v, attr in g.edges(data=True):
        edges.append({"source": u, "target": v, **attr})
    return {"nodes": nodes, "edges": edges}


def export_node_link_json(g: nx.DiGraph) -> dict:
    return nx.node_link_data(g)
