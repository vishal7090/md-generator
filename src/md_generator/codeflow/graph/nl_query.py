"""Rule-based natural language → graph intent (no LLM)."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from md_generator.codeflow.graph.analysis import event_flow_edges, references_from
from md_generator.codeflow.graph.enricher import called_by_transitive, impact_descendants
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph
from md_generator.codeflow.graph import relations as graph_rel


class ParsedNLQuery(TypedDict, total=False):
    type: str
    query: str
    target_hint: str | None
    raw: str


_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "for",
        "to",
        "of",
        "in",
        "on",
        "by",
        "is",
        "are",
        "what",
        "which",
        "who",
        "how",
        "find",
        "show",
        "list",
        "get",
        "me",
        "methods",
        "method",
        "flows",
        "flow",
        "calls",
        "call",
    },
)


def parse_nl_query(text: str) -> ParsedNLQuery:
    """Map free text to a structured intent."""
    raw = (text or "").strip()
    if not raw:
        return {"type": "unknown", "raw": raw}
    low = raw.lower()

    if "called by" in low or "who calls" in low:
        hint = _extract_target_hint(raw, ("called by", "who calls"))
        return {"type": "called_by", "target_hint": hint, "raw": raw}

    if "impact" in low or "affected" in low or "downstream" in low:
        hint = _extract_target_hint(raw, ("impact", "affected", "downstream"))
        return {"type": "impact", "target_hint": hint, "raw": raw}

    if "references" in low or "depends on" in low:
        hint = _extract_target_hint(raw, ("references", "depends on"))
        return {"type": "references", "target_hint": hint, "raw": raw}

    if "similar" in low or "related" in low or " like " in f" {low} ":
        return {"type": "semantic_search", "query": raw, "raw": raw}

    if "kafka" in low or ("async" in low and "call" in low):
        hint = _extract_target_hint(raw, ("kafka", "async"))
        return {"type": "event_flow", "target_hint": hint, "raw": raw}

    if "event" in low:
        hint = _extract_target_hint(raw, ("event",))
        return {"type": "event_flow", "target_hint": hint, "raw": raw}

    return {"type": "unknown", "raw": raw}


def _extract_target_hint(original: str, _keywords: tuple[str, ...]) -> str | None:
    """Pull a likely symbol/method fragment after common prepositions."""
    for pat in (
        r"for\s+`([^`]+)`",
        r"for\s+['\"]([^'\"]+)['\"]",
        r"for\s+([\w.]+(?:\s*::\s*[\w.]+)?)",
        r"by\s+`([^`]+)`",
        r"by\s+['\"]([^'\"]+)['\"]",
        r"by\s+([\w.]+)",
    ):
        m = re.search(pat, original, re.IGNORECASE)
        if m:
            h = m.group(1).strip()
            if h:
                return h
    tick = re.findall(r"`([^`]+)`", original)
    if tick:
        return tick[-1].strip()
    tokens = re.findall(r"[\w.]+", original)
    cand = [t for t in tokens if t.lower() not in _STOP and len(t) > 1]
    if cand:
        return cand[-1]
    return None


def resolve_target_hint(g: CodeflowGraph, hint: str | None, *, max_candidates: int = 50) -> tuple[str | None, list[str]]:
    """Return (unique_node_id, ambiguous_ids)."""
    if not hint or not str(hint).strip():
        return None, []
    h = str(hint).strip()
    h_low = h.lower()

    cands: list[str] = []
    for n, d in g.nodes(data=True):
        if not isinstance(n, str) or "::" not in n:
            continue
        if d.get("type") not in ("method", "entry"):
            continue
        if n == h or n.endswith("::" + h) or n.endswith("." + h) or n.endswith(h):
            cands.append(n)
            continue
        mn = str(d.get("method_name") or "")
        if mn and (mn == h or mn.lower() == h_low):
            cands.append(n)
            continue
        tail = n.split("::", 1)[-1] if "::" in n else n
        if h_low in tail.lower() or h_low in n.lower():
            cands.append(n)

    cands = sorted(set(cands))[:max_candidates]
    if len(cands) == 1:
        return cands[0], []
    if len(cands) == 0:
        return None, []
    return None, cands


def _name_substring_fallback(g: CodeflowGraph, query: str, *, top_k: int) -> list[dict[str, Any]]:
    q = query.lower()
    rows: list[tuple[str, float]] = []
    for n, d in g.nodes(data=True):
        if not isinstance(n, str) or "::" not in n:
            continue
        if d.get("type") not in ("method", "entry"):
            continue
        blob = f"{n} {d.get('method_name', '')} {d.get('class_name', '')}".lower()
        if q in blob:
            rows.append((n, 0.5))
    rows.sort(key=lambda x: x[0])
    out: list[dict[str, Any]] = []
    for nid, score in rows[:top_k]:
        d = dict(g.nodes[nid])
        out.append(
            {
                "node_id": nid,
                "score": score,
                "name": d.get("method_name"),
                "class_name": d.get("class_name"),
                "file_path": d.get("file_path"),
                "note": "substring_fallback",
            },
        )
    return out


def execute_nl_intent(
    g: CodeflowGraph,
    parsed: ParsedNLQuery,
    *,
    semantic_artifacts: Any | None,
    top_k: int = 15,
    list_cap: int = 80,
) -> dict[str, Any]:
    """Run the mapped intent; return JSON-serializable dict."""
    ptype = parsed.get("type", "unknown")
    raw = parsed.get("raw", "")

    if ptype == "unknown":
        return {"intent": "unknown", "raw": raw, "message": "No matching intent; try keywords: similar, impact, called by, event, references."}

    if ptype == "semantic_search":
        q = str(parsed.get("query") or raw)
        if semantic_artifacts is not None:
            from md_generator.codeflow.api.semantic_api import search_similar_serializable

            hits = search_similar_serializable(semantic_artifacts, q, top_k, g)
            return {"intent": "semantic_search", "query": q, "hits": hits, "source": "embeddings"}
        fb = _name_substring_fallback(g, q, top_k=top_k)
        return {
            "intent": "semantic_search",
            "query": q,
            "hits": fb,
            "source": "substring_fallback",
            "hint": "enable_embeddings for vector similarity",
        }

    if ptype in ("impact", "called_by", "references"):
        hint = parsed.get("target_hint")
        if ptype == "references" and not (hint and str(hint).strip()):
            return {
                "intent": "references",
                "message": "Specify a target, e.g. 'references for ClassName.methodName'.",
            }
        if ptype in ("impact", "called_by") and not (hint and str(hint).strip()):
            return {
                "intent": ptype,
                "message": "Specify a target, e.g. 'impact for pkg::Class.method' or 'called by MyService.foo'.",
            }
        nid, ambiguous = resolve_target_hint(g, hint)
        if ambiguous:
            return {
                "intent": ptype,
                "target_hint": hint,
                "ambiguous_candidates": ambiguous[:20],
                "message": "Multiple graph nodes match; narrow the name or use a full symbol id.",
            }
        if not nid:
            return {"intent": ptype, "target_hint": hint, "message": "Could not resolve target in graph."}

        if ptype == "impact":
            xs = impact_descendants(g, nid, list_cap)
            return {"intent": "impact", "target": nid, "nodes": xs, "truncated": len(xs) >= list_cap}
        if ptype == "called_by":
            xs = called_by_transitive(g, nid, list_cap)
            return {"intent": "called_by", "target": nid, "nodes": xs, "truncated": len(xs) >= list_cap}
        xs = references_from(g, nid)[:list_cap]
        return {"intent": "references", "target": nid, "nodes": xs, "truncated": len(xs) >= list_cap}

    if ptype == "event_flow":
        hint = parsed.get("target_hint")
        nid_resolved: str | None = None
        if hint:
            nid_resolved, amb = resolve_target_hint(g, hint)
            if amb:
                return {
                    "intent": "event_flow",
                    "target_hint": hint,
                    "ambiguous_candidates": amb[:20],
                    "message": "Multiple graph nodes match for event filter.",
                }
            if not nid_resolved:
                return {"intent": "event_flow", "target_hint": hint, "message": "Could not resolve target in graph."}
        edges_out: list[dict[str, Any]] = []
        for u, v, d in event_flow_edges(g):
            su, sv = str(u), str(v)
            if nid_resolved and nid_resolved not in (su, sv):
                continue
            row: dict[str, Any] = {"source": su, "target": sv, "relation": graph_rel.REL_EVENT}
            if isinstance(d, dict) and "event_role" in d:
                row["event_role"] = d["event_role"]
            edges_out.append(row)
            if len(edges_out) >= list_cap:
                break
        return {
            "intent": "event_flow",
            "target": nid_resolved,
            "target_hint": hint,
            "edges": edges_out,
            "truncated": len(edges_out) >= list_cap,
        }

    return {"intent": "unknown", "raw": raw}
