"""Stable Node/Edge JSON view over the internal DiGraph (does not replace graph-full.json)."""

from __future__ import annotations

from typing import Any

import networkx as nx

from md_generator.codeflow.graph import relations as rel

_REL_CALLS = rel.REL_CALLS
_REL_CONTAINS = rel.REL_CONTAINS
_KIND_FILE = "File"
_KIND_CLASS = "Class"
_KIND_METHOD = "Method"


def _file_node_id(rel_path: str) -> str:
    return f"file:{rel_path}"


def _class_node_id(rel_path: str, class_name: str) -> str:
    return f"class:{rel_path}::{class_name}"


def _node_kind_from_graph(d: dict[str, Any]) -> str:
    ek = d.get("entry_kind")
    if ek == "portlet":
        return "Portlet"
    if ek in ("api_rest",):
        return "API"
    if ek in ("kafka", "queue"):
        return "Event"
    if d.get("type") == "entry":
        return "API"
    if d.get("type") == "unknown" or d.get("unresolved"):
        return "Method"
    return _KIND_METHOD


def _tags_from_graph(d: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    ek = d.get("entry_kind")
    if ek:
        tags.append(str(ek))
    if d.get("unresolved"):
        tags.append("unresolved")
    et = d.get("type")
    if et:
        tags.append(str(et))
    return tags


def _ingest_prebuilt_structural_nodes(
    g: nx.DiGraph,
    nodes_out: list[dict[str, Any]],
    files_seen: set[str],
    classes_seen: set[tuple[str, str]],
) -> None:
    """Emit ``file:`` / ``class:`` / ``external:`` nodes already present on the DiGraph."""
    for nid, d in g.nodes(data=True):
        sid = str(nid)
        if sid.startswith("file:"):
            fp = sid[5:]
            if fp in files_seen:
                continue
            files_seen.add(fp)
            nodes_out.append(
                {
                    "id": sid,
                    "kind": _KIND_FILE,
                    "name": fp.split("/")[-1],
                    "qualified_name": fp,
                    "file_path": fp,
                    "line_start": None,
                    "line_end": None,
                    "language": d.get("language"),
                    "tags": list(d.get("tags") or ["file"]),
                    "confidence": float(d.get("confidence", 1.0)),
                },
            )
        elif sid.startswith("class:"):
            rest = sid[6:]
            if "::" not in rest:
                continue
            fp, cname = rest.split("::", 1)
            ck = (fp, cname)
            if ck in classes_seen:
                continue
            classes_seen.add(ck)
            nodes_out.append(
                {
                    "id": sid,
                    "kind": _KIND_CLASS,
                    "name": cname.split(".")[-1],
                    "qualified_name": cname,
                    "file_path": fp,
                    "line_start": None,
                    "line_end": None,
                    "language": d.get("language"),
                    "tags": list(d.get("tags") or ["class"]),
                    "confidence": float(d.get("confidence", 1.0)),
                },
            )
        elif sid.startswith("external:"):
            fq = sid[len("external::") :]
            nodes_out.append(
                {
                    "id": sid,
                    "kind": "External",
                    "name": fq.split(".")[-1],
                    "qualified_name": fq,
                    "file_path": None,
                    "line_start": None,
                    "line_end": None,
                    "language": d.get("language"),
                    "tags": list(d.get("tags") or ["external"]),
                    "confidence": float(d.get("confidence", 0.6)),
                },
            )


def to_stable_schema(g: nx.DiGraph) -> dict[str, Any]:
    """Return serializable schema with derived File/Class nodes and CONTAINS edges."""
    nodes_out: list[dict[str, Any]] = []
    edges_out: list[dict[str, Any]] = []
    seen_edge: set[tuple[str, str, str]] = set()

    files_seen: set[str] = set()
    classes_seen: set[tuple[str, str]] = set()

    def add_edge(src: str, tgt: str, kind: str, **extra: Any) -> None:
        key = (src, tgt, kind)
        if key in seen_edge:
            return
        seen_edge.add(key)
        row: dict[str, Any] = {"source": src, "target": tgt, "kind": kind, "condition": None, "confidence": 1.0}
        row.update(extra)
        edges_out.append(row)

    _ingest_prebuilt_structural_nodes(g, nodes_out, files_seen, classes_seen)

    # --- Derived File / Class nodes from symbol-bearing nodes ---
    for _nid, d in g.nodes(data=True):
        fp = (d.get("file_path") or "").strip()
        cn = d.get("class_name")
        if not fp:
            continue
        if fp not in files_seen:
            files_seen.add(fp)
            fid = _file_node_id(fp)
            nodes_out.append(
                {
                    "id": fid,
                    "kind": _KIND_FILE,
                    "name": fp.split("/")[-1],
                    "qualified_name": fp,
                    "file_path": fp,
                    "line_start": None,
                    "line_end": None,
                    "language": d.get("language"),
                    "tags": ["file"],
                    "confidence": 1.0,
                },
            )
        if cn:
            ck = (fp, str(cn))
            if ck not in classes_seen:
                classes_seen.add(ck)
                cid = _class_node_id(fp, str(cn))
                nodes_out.append(
                    {
                        "id": cid,
                        "kind": _KIND_CLASS,
                        "name": str(cn).split(".")[-1],
                        "qualified_name": str(cn),
                        "file_path": fp,
                        "line_start": None,
                        "line_end": None,
                        "language": d.get("language"),
                        "tags": ["class"],
                        "confidence": 1.0,
                    },
                )
                add_edge(_file_node_id(fp), cid, _REL_CONTAINS, confidence=1.0)

    # --- One row per graph node (method-like symbol) ---
    for nid, d in g.nodes(data=True):
        sym = str(nid)
        if sym.startswith(("file:", "class:", "external:")):
            continue
        fp = (d.get("file_path") or "").strip()
        cn = d.get("class_name")
        kind = _node_kind_from_graph(dict(d))
        nodes_out.append(
            {
                "id": sym,
                "kind": kind,
                "name": d.get("method_name") or sym.split("::")[-1],
                "qualified_name": sym.split("::", 1)[-1] if "::" in sym else sym,
                "file_path": fp or None,
                "line_start": None,
                "line_end": None,
                "language": d.get("language"),
                "tags": _tags_from_graph(dict(d)),
                "confidence": 0.7 if d.get("entry_kind") else 1.0,
            },
        )
        if fp and cn:
            add_edge(_class_node_id(fp, str(cn)), sym, _REL_CONTAINS, confidence=1.0)
        elif fp:
            add_edge(_file_node_id(fp), sym, _REL_CONTAINS, confidence=1.0)

    # --- Call edges (semantic CALLS only) ---
    for u, v, ed in g.edges(data=True):
        rel = ed.get("relation") or _REL_CALLS
        if rel != _REL_CALLS:
            continue
        edges_out.append(
            {
                "source": u,
                "target": v,
                "kind": _REL_CALLS,
                "condition": ed.get("condition"),
                "confidence": float(ed.get("confidence", 1.0)),
                "resolution": ed.get("resolution"),
                "unknown_call": ed.get("unknown_call"),
                "recursive": ed.get("recursive"),
            },
        )

    for u, v, ed in g.edges(data=True):
        rk = ed.get("relation") or _REL_CALLS
        if rk == _REL_CALLS:
            continue
        add_edge(
            u,
            v,
            str(rk),
            confidence=float(ed.get("confidence", 1.0)),
            condition=ed.get("condition"),
        )

    return {"nodes": nodes_out, "edges": edges_out}
