"""Git diff–based PR impact: changed files → seed graph nodes → downstream reachability."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import networkx as nx

from md_generator.codeflow.graph.analysis import dependency_reachability_subgraph
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph

PR_IMPACT_LIST_CAP = 500


class DiffAnalysisError(RuntimeError):
    """Raised when git diff cannot be run or returns an error."""


def _posix_rel(p: str) -> str:
    s = str(p).strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s


def git_changed_files(repo: Path, base: str, head: str) -> list[str]:
    """Return repo-relative POSIX paths changed between ``base`` and ``head`` (``git diff --name-only``)."""
    if not (repo / ".git").exists() and not _git_dir_exists(repo):
        raise DiffAnalysisError(f"Not a git checkout (no .git): {repo.resolve()}")
    b, h = str(base).strip(), str(head).strip()
    if not b or not h:
        raise DiffAnalysisError("diff base and head must be non-empty ref names or SHAs")
    try:
        r = subprocess.run(
            ["git", "-C", str(repo.resolve()), "diff", "--name-only", b, h],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except OSError as e:
        raise DiffAnalysisError(f"failed to spawn git: {e}") from e
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
        raise DiffAnalysisError(msg)
    return [_posix_rel(line) for line in r.stdout.splitlines() if line.strip()]


def _git_dir_exists(repo: Path) -> bool:
    """True if ``git rev-parse`` finds a git dir (supports worktrees)."""
    try:
        rr = subprocess.run(
            ["git", "-C", str(repo.resolve()), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return False
    return rr.returncode == 0 and bool((rr.stdout or "").strip())


def nodes_touching_files(
    g: CodeflowGraph,
    rel_paths: set[str],
    *,
    primary_repo_label: str | None = None,
) -> set[str]:
    """Nodes whose ``file_path`` matches a changed path (exact or under a changed path prefix).

    When ``primary_repo_label`` is set (multi-repo merge), only nodes with ``data.repo`` equal to it
    are considered, so identical relative paths in other repos are not mistaken for primary-repo changes.
    """
    norm_changed = {_posix_rel(p) for p in rel_paths if str(p).strip()}
    seeds: set[str] = set()
    for n, d in g.nodes(data=True):
        if primary_repo_label is not None and d.get("repo") != primary_repo_label:
            continue
        fp = d.get("file_path")
        if not fp:
            continue
        fp_n = _posix_rel(str(fp))
        for ch in norm_changed:
            if fp_n == ch or fp_n.startswith(ch + "/"):
                seeds.add(str(n))
                break
    return seeds


def diff_impact_nodes(
    g: CodeflowGraph,
    seeds: set[str],
    *,
    relations: frozenset[str] | None = None,
    include_contains: bool = False,
) -> set[str]:
    """Nodes downstream of ``seeds`` over the dependency reachability graph (same model as Markdown impact).

    When ``relations`` is ``None``, uses :func:`dependency_reachability_subgraph` (non-CONTAINS edges).
    When ``relations`` is set, builds a subgraph keeping only those relation kinds.
    """
    if relations is None:
        dg = dependency_reachability_subgraph(g, include_contains=include_contains)
    else:
        from md_generator.codeflow.graph.multigraph_utils import iter_multi_edges

        dg = nx.DiGraph()
        dg.add_nodes_from(g.nodes())
        for u, v, _k, ed in iter_multi_edges(g):
            r = str(ed.get("relation") or ed.get("kind") or "")
            if r in relations:
                dg.add_edge(u, v)
    impacted: set[str] = set()
    for s in seeds:
        if s in dg:
            impacted.update(nx.descendants(dg, s))
    return impacted | set(seeds)


def build_pr_impact_payload(
    g: CodeflowGraph,
    *,
    base: str,
    head: str,
    changed_files: list[str],
    primary_repo_label: str | None = None,
    include_contains: bool = False,
) -> dict[str, Any]:
    """Compute seed and impacted sets and return a JSON-serializable dict (with capped lists)."""
    ch_set = set(changed_files)
    seeds = nodes_touching_files(g, ch_set, primary_repo_label=primary_repo_label)
    impacted = diff_impact_nodes(g, seeds, include_contains=include_contains)
    cap = PR_IMPACT_LIST_CAP
    cf_sorted = sorted(changed_files)
    seeds_sorted = sorted(seeds)
    imp_sorted = sorted(impacted)
    return {
        "base": base,
        "head": head,
        "changed_files": cf_sorted[:cap],
        "changed_files_count": len(changed_files),
        "seed_nodes": seeds_sorted[:cap],
        "seed_nodes_count": len(seeds),
        "impacted_nodes": imp_sorted[:cap],
        "impacted_nodes_count": len(impacted),
    }
