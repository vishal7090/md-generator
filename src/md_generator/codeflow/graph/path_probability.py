"""Static and runtime-informed edge probabilities for CFG paths."""

from __future__ import annotations

from dataclasses import dataclass

from md_generator.codeflow.graph.cfg_model import CFG, CFGEdge


@dataclass
class PathProbConfig:
    """Default branch weights when no runtime data."""

    if_branch: float = 0.5
    loop_repeat: float = 0.6

    def loop_exit(self) -> float:
        return max(1e-12, min(1.0, 1.0 - self.loop_repeat))


def edge_static_prob(cfg: CFG, edge: CFGEdge, config: PathProbConfig) -> float:
    if edge.runtime_prob is not None:
        return max(1e-12, min(1.0, float(edge.runtime_prob)))
    src = cfg.nodes.get(edge.source)
    if src is None:
        return 1.0
    lab = (edge.label or "").lower()
    if src.kind == "IF":
        if lab in ("then", "else"):
            return max(1e-12, min(1.0, config.if_branch))
        if lab == "no_else":
            return 1.0
    if src.kind == "LOOP_HDR":
        if lab == "repeat":
            return max(1e-12, min(1.0, config.loop_repeat))
        if lab == "exit":
            return config.loop_exit()
    if src.kind == "SWITCH":
        n_out = len([e for e in cfg.edges if e.source == edge.source])
        return 1.0 / max(n_out, 1)
    return 1.0


def _first_edge(cfg: CFG, u: str, v: str) -> CFGEdge | None:
    for e in cfg.edges:
        if e.source == u and e.target == v:
            return e
    return None


def score_path(cfg: CFG, path: list[str], config: PathProbConfig) -> float:
    if len(path) < 2:
        return 1.0
    p = 1.0
    for i in range(len(path) - 1):
        e = _first_edge(cfg, path[i], path[i + 1])
        if e is None:
            continue
        p *= edge_static_prob(cfg, e, config)
    return p


def score_paths(cfg: CFG, paths: list[list[str]], config: PathProbConfig) -> list[tuple[list[str], float]]:
    return [(path, score_path(cfg, path, config)) for path in paths]
