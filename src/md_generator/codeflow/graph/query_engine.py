"""Minimal Cypher-like read-only queries over a ``MultiDiGraph``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges


@dataclass
class ParsedQuery:
    edge_pattern: str  # "CALLS", "IMPORTS", "*", or "IMPORTS|INHERITS"
    where_prefix: str | None
    max_results: int


def parse_simple_query(q: str, *, max_results: int = 5000) -> ParsedQuery:
    q = (q or "").strip()
    m = re.search(
        r"MATCH\s*\(\w+\)\s*-\[\s*([^\]]*?)\s*\]->\s*\(\w+\)",
        q,
        re.IGNORECASE | re.DOTALL,
    )
    edge_raw = (m.group(1).strip() if m else "*").strip()
    if not edge_raw or edge_raw == "*":
        pat = "*"
    else:
        pat = edge_raw.strip()
    wp = None
    wm = re.search(r"WHERE\s+(\S+)\s*=\s*\"([^\"]*)\"", q, re.IGNORECASE)
    if wm:
        wp = f'{wm.group(1).strip()}:{wm.group(2).strip()}'
    return ParsedQuery(edge_pattern=pat, where_prefix=wp, max_results=max_results)


def _edge_matches(pattern: str, relation: str) -> bool:
    if pattern == "*" or pattern == "":
        return True
    opts = [x.strip() for x in pattern.split("|") if x.strip()]
    return relation in opts


def _node_matches_where(nid: str, g: CodeflowGraph, where_prefix: str | None) -> bool:
    if not where_prefix:
        return True
    field, _, val = where_prefix.partition(":")
    field = field.strip().lower()
    val = val.strip()
    if field == "name":
        d = g.nodes.get(nid, {})
        return str(d.get("name", "")) == val or str(d.get("method_name", "")) == val
    if field in ("id", "nid"):
        return str(nid) == val or str(nid).endswith(val)
    return True


def execute_query(g: CodeflowGraph, q: str, *, max_results: int = 5000) -> list[dict[str, Any]]:
    pq = parse_simple_query(q, max_results=max_results)
    out: list[dict[str, Any]] = []
    for u, v, ek, d in iter_multi_edges(g):
        rel = str(d.get("relation") or d.get("kind") or "")
        if not _edge_matches(pq.edge_pattern, rel):
            continue
        if pq.where_prefix and not (
            _node_matches_where(str(u), g, pq.where_prefix) or _node_matches_where(str(v), g, pq.where_prefix)
        ):
            continue
        out.append(
            {
                "source": u,
                "target": v,
                "key": ek,
                "relation": rel,
                "confidence": d.get("confidence"),
            },
        )
        if len(out) >= pq.max_results:
            break
    return out
