"""Resolve ``external::…`` IMPORTS across merged multi-repo graphs using package prefix hints."""

from __future__ import annotations

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.dependency_builder import _candidate_relpaths, _lang_from_path
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, edge_payload, find_edge_key_with_relation, iter_multi_edges

_EXT_MARKER = "::external::"


def _external_module_from_target(v: str) -> str | None:
    """``external::pkg`` (single-repo) or ``lab::external::pkg`` (after :func:`merge_graphs`)."""
    if v.startswith("external::"):
        return v[len("external::") :]
    if _EXT_MARKER in v:
        return v.split(_EXT_MARKER, 1)[1]
    return None


def _file_index(g: CodeflowGraph) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for n in g.nodes():
        s = str(n)
        if "::file:" not in s:
            continue
        lab, rest = s.split("::file:", 1)
        out[(lab, rest.replace("\\", "/"))] = s
    return out


def _repos_in_graph(g: CodeflowGraph) -> set[str]:
    labs: set[str] = set()
    for _n, d in g.nodes(data=True):
        r = d.get("repo")
        if isinstance(r, str) and r.strip():
            labs.add(r.strip())
    return labs


def _longest_hint(mod: str, hints: dict[str, str]) -> tuple[str, str] | None:
    best_pfx: str | None = None
    best_lab: str | None = None
    best_len = -1
    for pfx, lab in hints.items():
        k = str(pfx).strip()
        if not k:
            continue
        if mod == k or mod.startswith(k + "."):
            if len(k) > best_len:
                best_len = len(k)
                best_pfx = k
                best_lab = str(lab).strip()
    if best_pfx is None or not best_lab:
        return None
    return best_pfx, best_lab


def _java_paths(mod: str) -> list[str]:
    if not mod or mod.startswith("relative::"):
        return []
    if "$" in mod:
        outer = mod.split("$", 1)[0]
        base = outer.replace(".", "/")
        return [base + ".java", base + ".kt"]
    base = mod.replace(".", "/")
    return [base + ".java", base + ".kt"]


def _paths_for_module(mod: str, language: str) -> list[str]:
    cands: list[str] = []
    if language == "java" or (language == "mixed" and "." in mod and "/" not in mod and not mod.endswith(".py")):
        cands.extend(_java_paths(mod))
    cands.extend(_candidate_relpaths(mod, language if language != "mixed" else "python"))
    cands.extend(_candidate_relpaths(mod, "typescript"))
    # de-dup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def resolve_cross_repo_imports(
    g: CodeflowGraph,
    package_hints: dict[str, str] | None,
) -> int:
    """Add ``REL_CROSS_REPO_IMPORT`` edges from sources to resolved ``file:`` nodes in hinted repos."""
    if not package_hints:
        return 0
    hints = {str(k).strip(): str(v).strip() for k, v in package_hints.items() if str(k).strip() and str(v).strip()}
    if not hints:
        return 0
    known_repos = _repos_in_graph(g)
    idx = _file_index(g)
    added = 0
    for u, v, _k, d in list(iter_multi_edges(g)):
        if d.get("relation") != rel.REL_IMPORTS:
            continue
        vs = str(v)
        mod = _external_module_from_target(vs)
        if mod is None:
            continue
        if mod.startswith("relative::") or mod.endswith(".*") or mod == "*" or "::*" in mod:
            continue
        if u not in g:
            continue
        src_repo = g.nodes[u].get("repo")
        if not isinstance(src_repo, str) or not src_repo.strip():
            continue
        src_repo = src_repo.strip()
        hit = _longest_hint(mod, hints)
        if hit is None:
            continue
        _pfx, tgt_lab = hit
        if tgt_lab not in known_repos:
            continue
        if tgt_lab == src_repo:
            continue
        lang_u = str(g.nodes[u].get("language") or "mixed")
        if isinstance(u, str) and "::file:" in u:
            fp = u.split("::file:", 1)[1]
            lang_u = _lang_from_path(fp.replace("\\", "/"))
        cands = _paths_for_module(mod, lang_u)
        matches = [idx[(tgt_lab, p)] for p in cands if (tgt_lab, p) in idx]
        matches = list(dict.fromkeys(matches))
        if len(matches) != 1:
            continue
        tgt_id = matches[0]
        if find_edge_key_with_relation(g, u, tgt_id, rel.REL_CROSS_REPO_IMPORT) is not None:
            continue
        g.add_edge(
            u,
            tgt_id,
            **edge_payload(
                relation=rel.REL_CROSS_REPO_IMPORT,
                condition=None,
                confidence=min(0.95, float(d.get("confidence", 0.75)) + 0.05),
                type="structural",
                labels=[],
                async_=False,
                unknown_call=False,
                recursive=False,
                structural_line=d.get("structural_line"),
                file_layer=bool(d.get("file_layer")),
                cross_repo=True,
                resolved_from=vs,
                hint_prefix=hit[0],
            ),
        )
        added += 1
    return added
