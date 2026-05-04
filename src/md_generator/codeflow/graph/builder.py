from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.models.ir import CallSite, FileParseResult, StructuralEdge

_LOG = logging.getLogger(__name__)


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


def _call_edge_confidence(call: CallSite, callee_id: str) -> float:
    """AST static -> 1.0, dynamic -> 0.7, unknown / unresolved -> 0.5."""
    if str(callee_id).startswith("unknown::"):
        return 0.5
    if call.resolution == "unknown":
        return 0.5
    if call.resolution == "dynamic":
        return 0.7
    return 1.0


@dataclass(slots=True)
class GraphBuildResult:
    graph: nx.DiGraph
    project_root: Path


def _build_java_fqn_index(parse_results: list[FileParseResult], root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Map dotted FQN -> class node id and FQN -> defining file rel path (Java only)."""
    fqn_to_class: dict[str, str] = {}
    fqn_to_file: dict[str, str] = {}
    for fr in parse_results:
        if fr.language != "java" or not (fr.java_package or "").strip():
            continue
        pkg = fr.java_package.strip()
        rel = _safe_rel(fr.path, root)
        for sid in fr.symbol_ids:
            if "::" not in sid:
                continue
            _, rest = sid.split("::", 1)
            if "." not in rest:
                continue
            fq_class = rest.rsplit(".", 1)[0]
            fqn = f"{pkg}.{fq_class}" if fq_class else pkg
            cid = f"class:{rel}::{fq_class}"
            fqn_to_class.setdefault(fqn, cid)
            fqn_to_file.setdefault(fqn, rel)
    return fqn_to_class, fqn_to_file


def _ensure_structural_vertex(g: nx.DiGraph, node_id: str, language: str) -> None:
    if g.has_node(node_id):
        return
    if node_id.startswith("file:"):
        fp = node_id[5:]
        g.add_node(
            node_id,
            id=node_id,
            type="file",
            kind="File",
            name=fp.split("/")[-1],
            class_name=None,
            method_name=None,
            file_path=fp,
            language=language,
            tags=["file"],
        )
    elif node_id.startswith("class:"):
        rest = node_id[6:]
        if "::" in rest:
            fp, cname = rest.split("::", 1)
        else:
            fp, cname = "", rest
        g.add_node(
            node_id,
            id=node_id,
            type="class",
            kind="Class",
            name=cname.split(".")[-1],
            class_name=cname,
            method_name=None,
            file_path=fp,
            language=language,
            tags=["class"],
        )
    elif node_id.startswith("external:"):
        g.add_node(
            node_id,
            id=node_id,
            type="external",
            kind="External",
            name=node_id[9:].split(".")[-1],
            class_name=None,
            method_name=None,
            file_path="",
            language=language,
            tags=["external"],
        )


def _rewrite_structural_target(
    target_id: str,
    relation: str,
    fqn_to_class: dict[str, str],
    fqn_to_file: dict[str, str],
) -> tuple[str, float]:
    if not target_id.startswith("external::"):
        return target_id, 1.0
    fqn = target_id[len("external::") :]
    if relation in (rel.REL_INHERITS, rel.REL_IMPLEMENTS) and fqn in fqn_to_class:
        return fqn_to_class[fqn], 1.0
    if relation == rel.REL_IMPORTS and fqn in fqn_to_file:
        return f"file:{fqn_to_file[fqn]}", 1.0
    return target_id, float(0.6 if relation == rel.REL_IMPORTS else 0.7)


def _merge_structural_edges(
    g: nx.DiGraph,
    parse_results: list[FileParseResult],
    root: Path,
    *,
    include_structural: bool,
) -> None:
    if not include_structural:
        return
    fqn_to_class, fqn_to_file = _build_java_fqn_index(parse_results, root)
    for fr in parse_results:
        for se in fr.structural_edges:
            new_tgt, rw_conf = _rewrite_structural_target(
                se.target_id, se.relation, fqn_to_class, fqn_to_file
            )
            conf = float(min(se.confidence, rw_conf) if new_tgt != se.target_id else se.confidence)
            src, tgt = se.source_id, new_tgt
            _ensure_structural_vertex(g, src, fr.language)
            _ensure_structural_vertex(g, tgt, fr.language)
            if g.has_edge(src, tgt):
                ed = g.edges[src, tgt]
                if ed.get("relation") == rel.REL_CALLS:
                    continue
                ed["confidence"] = min(float(ed.get("confidence", 1.0)), conf)
            else:
                g.add_edge(
                    src,
                    tgt,
                    type="structural",
                    relation=se.relation,
                    condition=None,
                    labels=[],
                    async_=False,
                    unknown_call=False,
                    recursive=False,
                    confidence=conf,
                    structural_line=se.line,
                )


def build_graph(
    parse_results: list[FileParseResult],
    project_root: Path,
    *,
    include_structural: bool = False,
) -> GraphBuildResult:
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
            conf = _call_edge_confidence(call, callee_id)
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
                ed["relation"] = "CALLS"
                ed["confidence"] = min(float(ed.get("confidence", 1.0)), conf)
            else:
                g.add_edge(
                    call.caller_id,
                    callee_id,
                    type=edge_type,
                    relation="CALLS",
                    resolution=call.resolution,
                    condition=cond,
                    labels=[cond] if cond else [],
                    async_=call.is_async,
                    unknown_call=unknown_call,
                    recursive=recursive,
                    confidence=conf,
                )

    _merge_structural_edges(g, parse_results, root, include_structural=include_structural)

    if include_structural and _LOG.isEnabledFor(logging.DEBUG):
        n_call = sum(1 for _, _, d in g.edges(data=True) if d.get("relation", rel.REL_CALLS) == rel.REL_CALLS)
        n_imp = sum(1 for _, _, d in g.edges(data=True) if d.get("relation") == rel.REL_IMPORTS)
        n_inh = sum(1 for _, _, d in g.edges(data=True) if d.get("relation") == rel.REL_INHERITS)
        n_impl = sum(1 for _, _, d in g.edges(data=True) if d.get("relation") == rel.REL_IMPLEMENTS)
        _LOG.debug(
            "graph built: nodes=%s edges=%s CALLS=%s IMPORTS=%s INHERITS=%s IMPLEMENTS=%s",
            g.number_of_nodes(),
            g.number_of_edges(),
            n_call,
            n_imp,
            n_inh,
            n_impl,
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
