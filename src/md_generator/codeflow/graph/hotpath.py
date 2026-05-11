"""Score CFG paths using runtime edge counts (hot-path ranking)."""

from __future__ import annotations

from typing import Any

from md_generator.codeflow.graph.cfg_model import CFG


def normalize_runtime_trace(trace: dict[str, Any] | None) -> dict[str, float]:
    """Merge ``counts`` and alias ``edges`` into ``source->target`` -> float weights.

    **Input:** a dict with optional ``counts`` and/or ``edges`` sub-dicts. Each sub-dict maps
    string keys ``"cfg_u->cfg_v"`` to numeric observation counts. The two blocks are merged
    (later keys overwrite on collision). Keys without ``->`` are ignored.

    **Output:** flat ``{"u->v": float, ...}`` for scoring paths and anomalies.

    Matches :func:`md_generator.codeflow.graph.runtime_integration.apply_runtime_weights`.
    """
    if not trace or not isinstance(trace, dict):
        return {}
    raw: dict[str, Any] = {}
    for key in ("counts", "edges"):
        block = trace.get(key)
        if isinstance(block, dict):
            raw.update(block)
    out: dict[str, float] = {}
    for k, v in raw.items():
        ks = str(k).strip()
        if "->" not in ks:
            continue
        try:
            out[ks] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def score_cfg_paths(paths: list[list[str]], edge_counts: dict[str, float]) -> list[tuple[list[str], float]]:
    """Sum observed counts along each path (consecutive CFG node pairs)."""
    scored: list[tuple[list[str], float]] = []
    for path in paths:
        s = 0.0
        for i in range(len(path) - 1):
            key = f"{path[i]}->{path[i + 1]}"
            s += edge_counts.get(key, 0.0)
        scored.append((path, s))
    scored.sort(key=lambda x: -x[1])
    return scored


def top_hot_paths(
    paths: list[list[str]],
    edge_counts: dict[str, float],
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Return top-N paths by aggregate runtime count along CFG edges."""
    if not paths:
        return []
    scored = score_cfg_paths(paths, edge_counts)
    out: list[dict[str, Any]] = []
    for path, score in scored[: max(1, top_n)]:
        out.append(
            {
                "nodes": list(path),
                "score": float(score),
                "edge_keys": [f"{path[i]}->{path[i + 1]}" for i in range(len(path) - 1)],
            },
        )
    return out


def hot_paths_payload(
    cfg: CFG,
    paths: list[list[str]],
    trace: dict[str, Any] | None,
    *,
    top_n: int = 5,
    path_truncated: bool = False,
) -> dict[str, Any]:
    """Build JSON payload for ``runtime-insights.json`` hot-path section."""
    counts = normalize_runtime_trace(trace)
    ranked = top_hot_paths(paths, counts, top_n=top_n)
    return {
        "hot_paths": ranked,
        "hot_paths_meta": {
            "paths_truncated": path_truncated,
            "trace_edges_loaded": len(counts),
            "cfg_edges": len(cfg.edges),
            "note": "Score sums runtime trace counts on CFG edges (source->target keys).",
        },
    }
