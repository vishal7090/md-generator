"""Deterministic, rule-based labels for graph communities (no LLM)."""

from __future__ import annotations

import re
from typing import Any

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges

_MAX_LABEL_LEN = 80


def cluster_label_histogram_markdown(
    community_profiles: list[dict[str, Any]],
    *,
    top_n: int = 15,
) -> list[str]:
    """Markdown lines: member counts per rule-based ``label`` (deterministic sort)."""
    counts: dict[str, int] = {}
    for p in community_profiles:
        lab = str(p.get("label") or "").strip()
        if not lab:
            lab = f"community_{p.get('id', '?')}"
        n = len(p.get("members") or [])
        counts[lab] = counts.get(lab, 0) + n
    ranked = sorted(counts.items(), key=lambda t: (-t[1], t[0]))[: max(1, top_n)]
    lines = [
        "## Cluster label distribution",
        "",
        "_Rule-based labels; counts are community members._",
        "",
    ]
    for lab, c in ranked:
        lines.append(f"- `{lab}`: {c}")
    lines.append("")
    return lines

# Ordered: first match wins (deterministic).
_PATH_BUCKETS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)test(s)?/", re.I), "tests"),
    (re.compile(r"(^|/)src/test/", re.I), "tests"),
    (re.compile(r"portlet", re.I), "portlet"),
    (re.compile(r"controller", re.I), "controller"),
    (re.compile(r"\bservice\b", re.I), "service"),
    (re.compile(r"repository|repo\b|dao\b", re.I), "data_access"),
    (re.compile(r"api[/\\]|/api\b", re.I), "api"),
    (re.compile(r"model|entity|domain", re.I), "model"),
    (re.compile(r"util|helper|common", re.I), "util"),
]


def _posix(fp: str) -> str:
    return str(fp).strip().replace("\\", "/")


def _file_paths_for_members(g: CodeflowGraph, members: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for nid in members:
        fp = ""
        if isinstance(nid, str) and "::file:" in nid:
            fp = _posix(nid.split("::file:", 1)[1])
        elif isinstance(nid, str) and nid.startswith("file:"):
            fp = _posix(nid[5:])
        elif isinstance(nid, str) and nid in g:
            fp = _posix(str(g.nodes[nid].get("file_path") or ""))
        if fp and fp not in seen:
            seen.add(fp)
            out.append(fp)
    return sorted(out)


def _longest_common_dir_prefix(paths: list[str]) -> str:
    if not paths:
        return ""
    parts_list = [p.split("/") for p in paths if p]
    if not parts_list:
        return ""
    min_len = min(len(x) for x in parts_list)
    common: list[str] = []
    for i in range(min_len):
        seg = parts_list[0][i]
        if all(len(pl) > i and pl[i] == seg for pl in parts_list):
            common.append(seg)
        else:
            break
    return "/".join(common) if common else ""


def _dominant_path_bucket(paths: list[str]) -> str | None:
    scores: dict[str, int] = {}
    for fp in paths:
        for pat, name in _PATH_BUCKETS:
            if pat.search(fp):
                scores[name] = scores.get(name, 0) + 1
                break
    if not scores:
        return None
    best_n = max(scores.values())
    candidates = sorted(k for k, v in scores.items() if v == best_n)
    return candidates[0]


def _subgraph_degree_stats(g: CodeflowGraph, members: set[str]) -> tuple[int, int, int]:
    """Counts of internal CALLS, IMPORTS, other edges between members (undirected count once)."""
    calls = imports = other = 0
    for u, v, _k, d in iter_multi_edges(g):
        if str(u) not in members or str(v) not in members:
            continue
        r = str(d.get("relation") or d.get("kind") or "")
        if r == rel.REL_CALLS:
            calls += 1
        elif r == rel.REL_IMPORTS:
            imports += 1
        else:
            other += 1
    return calls, imports, other


def label_community(
    g: CodeflowGraph,
    members: list[str],
    *,
    mode: str,
    semantic_majority: int | None = None,
) -> dict[str, Any]:
    """Return ``label``, ``confidence`` (rule priority 0..1), and ``signals`` for one community."""
    mem = sorted({str(m) for m in members if m})
    paths = _file_paths_for_members(g, mem)
    lcp = _longest_common_dir_prefix(paths)
    bucket = _dominant_path_bucket(paths)
    mem_set = set(mem)
    calls_e, imp_e, oth_e = _subgraph_degree_stats(g, mem_set) if mem_set else (0, 0, 0)
    total_e = calls_e + imp_e + oth_e
    call_share = (calls_e / total_e) if total_e else 0.0
    imp_share = (imp_e / total_e) if total_e else 0.0

    parts: list[str] = []
    if bucket:
        parts.append(bucket)
    if lcp:
        tail = lcp if len(lcp) <= 48 else lcp[:45] + "…"
        parts.append(tail)
    elif paths:
        top = paths[0]
        parts.append(top.split("/")[0] if "/" in top else top)
    else:
        parts.append("mixed_symbols")

    if call_share >= 0.5 and total_e:
        parts.append("call_dense")
    elif imp_share >= 0.5 and total_e:
        parts.append("import_dense")

    label = "/".join(parts) if parts else "cluster"
    if semantic_majority is not None:
        label = f"{label}|sem{int(semantic_majority)}"

    label = label.replace("\n", " ").strip()
    if len(label) > _MAX_LABEL_LEN:
        label = label[: _MAX_LABEL_LEN - 1] + "…"

    confidence = 0.75 if bucket and lcp else 0.6 if bucket or lcp else 0.45
    signals: dict[str, Any] = {
        "member_count": len(mem),
        "file_paths_sample": paths[:5],
        "longest_common_dir": lcp or None,
        "path_bucket": bucket,
        "internal_edges": {"calls": calls_e, "imports": imp_e, "other": oth_e},
        "cluster_mode": mode,
    }
    return {"label": label, "confidence": float(confidence), "signals": signals}


def _normalize_communities(
    comm_payload: list[Any],
    mode: str,
) -> tuple[list[list[str]], dict[frozenset[str], int | None]]:
    """Extract member lists and optional hybrid semantic_majority by member set."""
    hybrid_meta: dict[frozenset[str], int | None] = {}
    rows: list[list[str]] = []
    for item in comm_payload:
        if mode == "hybrid" and isinstance(item, dict) and "members" in item:
            mem = [str(x) for x in item["members"]]
            fs = frozenset(mem)
            sm = item.get("semantic_majority")
            hybrid_meta[fs] = int(sm) if sm is not None else None
            rows.append(mem)
        elif isinstance(item, list):
            rows.append([str(x) for x in item])
    return rows, hybrid_meta


def stable_ordered_communities(
    g: CodeflowGraph,
    comm_payload: list[Any],
    mode: str,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Sort communities deterministically and attach rule-based profiles.

    Returns ``(new_payload, community_profiles)`` where profiles have
    ``id``, ``label``, ``confidence``, ``members``, ``signals``.
    """
    if not comm_payload:
        return [], []

    rows, hybrid_meta = _normalize_communities(comm_payload, mode)
    decorated: list[tuple[str, tuple[str, ...], list[str], dict[str, Any]]] = []
    for mem in rows:
        fs = frozenset(mem)
        sm = hybrid_meta.get(fs) if mode == "hybrid" else None
        prof = label_community(g, mem, mode=mode, semantic_majority=sm)
        label = str(prof["label"])
        key_mem = tuple(sorted(mem))
        decorated.append((label, key_mem, mem, prof))

    decorated.sort(key=lambda t: (t[0], t[1]))

    profiles: list[dict[str, Any]] = []
    new_lists: list[list[str]] = []

    for i, (_lab, _km, mem, prof) in enumerate(decorated):
        profiles.append(
            {
                "id": i,
                "label": prof["label"],
                "confidence": prof["confidence"],
                "members": sorted(mem),
                "signals": prof["signals"],
            },
        )
        new_lists.append(sorted(mem))

    if mode == "hybrid":
        new_payload: list[Any] = []
        for i, mem in enumerate(new_lists):
            fs = frozenset(mem)
            sm = hybrid_meta.get(fs)
            row: dict[str, Any] = {"id": i, "members": mem}
            if sm is not None:
                row["semantic_majority"] = sm
            new_payload.append(row)
    else:
        new_payload = new_lists  # type: ignore[assignment]

    return new_payload, profiles


def file_cluster_label_strings(
    g: CodeflowGraph,
    community_profiles: list[dict[str, Any]],
) -> dict[str, str]:
    """Map ``file_path`` (posix) → community ``label`` string."""
    out: dict[str, str] = {}
    for p in community_profiles:
        cid = int(p.get("id", -1))
        label = str(p.get("label", f"cluster_{cid}"))
        for nid in p.get("members") or []:
            if not isinstance(nid, str):
                continue
            fp = ""
            if "::file:" in nid:
                fp = _posix(nid.split("::file:", 1)[1])
            elif nid.startswith("file:"):
                fp = _posix(nid[5:])
            elif nid in g:
                fp = _posix(str(g.nodes[nid].get("file_path") or ""))
            if fp:
                out[fp] = label
    return out
