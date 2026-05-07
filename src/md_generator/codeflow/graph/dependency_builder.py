"""Best-effort resolution of ``external::…`` IMPORTS targets to ``file:`` vertices (single-root scans)."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import (
    CodeflowGraph,
    edge_payload,
    find_edge_key_with_relation,
    iter_multi_edges,
    iter_out_edges,
)
from md_generator.codeflow.models.ir import FileParseResult


def _rel_file(fr_path: Path, root: Path) -> str:
    try:
        return fr_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return fr_path.as_posix()


def _collect_relpaths(parse_results: list[FileParseResult], root: Path) -> set[str]:
    return {_rel_file(fr.path, root) for fr in parse_results}


def _lang_from_path(rel: str) -> str:
    low = rel.lower()
    if low.endswith(".py"):
        return "python"
    if low.endswith((".ts", ".tsx", ".mts")):
        return "typescript"
    if low.endswith((".js", ".jsx", ".mjs", ".cjs")):
        return "javascript"
    return "mixed"


def _candidate_relpaths(module: str, language: str) -> list[str]:
    if not module or module.startswith("relative::") or module.endswith(".*"):
        return []
    if module.startswith((".", "/", "@")):
        return []
    parts = module.split(".")
    if not parts:
        return []
    out: list[str] = []
    if language == "python":
        out.append("/".join(parts) + ".py")
        if len(parts) > 1:
            out.append("/".join(parts[:-1]) + "/" + parts[-1] + ".py")
        out.append("/".join(parts) + "/__init__.py")
    elif language in ("javascript", "typescript", "tsx"):
        base = "/".join(parts)
        out.extend(
            [
                base + ".ts",
                base + ".tsx",
                base + ".js",
                base + ".jsx",
                base + "/index.ts",
                base + "/index.tsx",
                base + "/index.js",
            ],
        )
    return out


def apply_import_resolution(g: CodeflowGraph, parse_results: list[FileParseResult], root: Path) -> int:
    """Add resolved ``file:``→``file:`` IMPORTS where ``external::`` maps uniquely to a parsed file.

    Runs after structural merge; complements Java FQN rewriting in ``build_graph``.
    """
    from md_generator.codeflow.graph.builder import _ensure_structural_vertex

    existing = _collect_relpaths(parse_results, root)
    added = 0
    for u, v, _k, d in list(iter_multi_edges(g)):
        if d.get("relation") != rel.REL_IMPORTS:
            continue
        if d.get("import_resolution"):
            continue
        if not (isinstance(u, str) and str(u).startswith("file:")):
            continue
        vs = str(v)
        if not vs.startswith("external::"):
            continue
        mod = vs[len("external::") :]
        lang_u = "mixed"
        if isinstance(u, str) and u.startswith("file:"):
            fp_u = u[5:]
            lang_u = _lang_from_path(fp_u)
        elif u in g:
            lang_u = str(g.nodes[u].get("language") or "mixed")
        cands = _candidate_relpaths(mod, lang_u)
        hits = list(dict.fromkeys([c for c in cands if c in existing]))
        if len(hits) != 1:
            continue
        rel_hit = hits[0]
        new_tgt = f"file:{rel_hit}"
        lang_t = _lang_from_path(rel_hit)
        _ensure_structural_vertex(g, str(u), lang_u)
        _ensure_structural_vertex(g, new_tgt, lang_t)
        if find_edge_key_with_relation(g, u, new_tgt, rel.REL_IMPORTS) is not None:
            continue
        g.add_edge(
            u,
            new_tgt,
            **edge_payload(
                relation=rel.REL_IMPORTS,
                condition=None,
                confidence=min(0.98, float(d.get("confidence", 0.8)) + 0.1),
                type="structural",
                labels=[],
                async_=False,
                unknown_call=False,
                recursive=False,
                structural_line=d.get("structural_line"),
                file_layer=False,
                import_resolution=True,
                resolved_from=vs,
            ),
        )
        added += 1
    return added


def file_import_successors(g: CodeflowGraph, file_node_id: str, *, cap: int = 200) -> list[str]:
    """Out-neighbors from a ``file:`` node along IMPORTS (any layer), deduped and capped."""
    if file_node_id not in g:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for _u, v, _k, d in iter_out_edges(g, file_node_id):
        if d.get("relation") != rel.REL_IMPORTS:
            continue
        vs = str(v)
        if vs in seen:
            continue
        seen.add(vs)
        out.append(vs)
        if len(out) >= cap:
            break
    return out


def class_structural_successors(
    g: CodeflowGraph,
    class_node_id: str,
    relations: frozenset[str],
    *,
    cap: int = 50,
) -> list[tuple[str, str]]:
    """Return (relation, target_id) for INHERITS / IMPLEMENTS (etc.) out-edges from a class vertex."""
    if class_node_id not in g:
        return []
    rows: list[tuple[str, str]] = []
    for _u, v, _k, d in iter_out_edges(g, class_node_id):
        r = str(d.get("relation") or "")
        if r not in relations:
            continue
        rows.append((r, str(v)))
        if len(rows) >= cap:
            break
    return rows
