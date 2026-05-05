"""Enumerate bounded execution paths over a CFG (no AST imports)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from md_generator.codeflow.graph.cfg_model import CFG, CFGEdge, CFGNode


@dataclass
class PathResult:
    paths: list[list[str]] = field(default_factory=list)
    truncated: bool = False


def _outgoing(cfg: CFG, node_id: str) -> list[CFGEdge]:
    return [e for e in cfg.edges if e.source == node_id]


def _is_loop_header(n: CFGNode) -> bool:
    return n.kind in ("LOOP_HDR", "LOOP")


def enumerate_paths(
    cfg: CFG,
    start_id: str,
    end_id: str,
    *,
    max_paths: int = 100,
    max_depth: int = 1000,
    max_loop_visits: int = 2,
) -> PathResult:
    """DFS from ``start_id`` to ``end_id`` with caps; ``paths`` are node-id sequences."""
    res = PathResult()
    if start_id not in cfg.nodes or end_id not in cfg.nodes:
        return res

    loop_visits: dict[str, int] = defaultdict(int)

    def dfs(node_id: str, path: list[str], depth: int) -> None:
        if len(res.paths) >= max_paths:
            res.truncated = True
            return
        if depth > max_depth:
            res.truncated = True
            return

        path.append(node_id)
        if node_id == end_id:
            res.paths.append(list(path))
            path.pop()
            return

        node = cfg.nodes[node_id]
        outs = _outgoing(cfg, node_id)

        if _is_loop_header(node):
            loop_visits[node_id] += 1
            if loop_visits[node_id] > max_loop_visits:
                for e in outs:
                    lab = (e.label or "").lower()
                    if lab in ("exit", "false", "break", "no_else"):
                        dfs(e.target, path, depth + 1)
                loop_visits[node_id] -= 1
                path.pop()
                return

        for e in outs:
            dfs(e.target, path, depth + 1)

        if _is_loop_header(node):
            loop_visits[node_id] -= 1

        path.pop()

    dfs(start_id, [], 0)
    return res


def find_cfg_start_id(cfg: CFG) -> str | None:
    for nid, n in cfg.nodes.items():
        if n.kind == "START":
            return nid
    return None


def find_cfg_end_id(cfg: CFG) -> str | None:
    for nid, n in cfg.nodes.items():
        if n.kind == "END":
            return nid
    return None
