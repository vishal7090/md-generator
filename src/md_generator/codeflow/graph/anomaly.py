"""Runtime-frequency anomalies and optional semantic outliers."""

from __future__ import annotations

from typing import Any

from md_generator.codeflow.graph.cfg_model import CFG
from md_generator.codeflow.graph.hotpath import normalize_runtime_trace


def rare_cfg_edges(
    cfg: CFG,
    trace: dict[str, Any] | None,
    *,
    frequency_threshold: float = 0.05,
) -> list[dict[str, Any]]:
    """Flag CFG edges whose share of total observed trace mass is below ``frequency_threshold``.

    Share is ``count(edge) / sum(all trace counts)``. Missing keys count as 0.
    """
    counts = normalize_runtime_trace(trace)
    total = sum(counts.values())
    if total <= 0:
        return []

    anomalies: list[dict[str, Any]] = []
    for e in cfg.edges:
        key = f"{e.source}->{e.target}"
        cnt = counts.get(key, 0.0)
        freq = cnt / total
        if freq < frequency_threshold:
            anomalies.append(
                {
                    "source": e.source,
                    "target": e.target,
                    "label": e.label,
                    "count": float(cnt),
                    "frequency": float(freq),
                    "threshold": float(frequency_threshold),
                },
            )
    return anomalies


def semantic_outlier_nodes(
    artifacts: Any,
    *,
    distance_threshold: float = 0.7,
) -> list[dict[str, Any]]:
    """Nodes whose embedding cosine distance from their KMeans label centroid exceeds threshold.

    Uses ``1 - dot`` on L2-normalized rows. Requires numpy and ``SemanticArtifacts``.
    """
    try:
        import numpy as np
    except ImportError:
        return []

    labels = getattr(artifacts, "labels", None) or {}
    node_ids = getattr(artifacts, "node_ids", None) or []
    index = getattr(artifacts, "index", None)
    if index is None or index.vectors is None or not node_ids:
        return []

    vecs = np.asarray(index.vectors, dtype=np.float64)
    if vecs.ndim != 2:
        return []

    by_label: dict[int, list[int]] = {}
    for i, nid in enumerate(node_ids):
        lab = labels.get(nid)
        if lab is None:
            continue
        by_label.setdefault(int(lab), []).append(i)

    centroids: dict[int, np.ndarray] = {}
    for lab, idxs in by_label.items():
        sub = vecs[idxs]
        c = sub.mean(axis=0)
        n = np.linalg.norm(c)
        centroids[lab] = c / n if n > 1e-9 else c

    out: list[dict[str, Any]] = []
    for i, nid in enumerate(node_ids):
        lab = labels.get(nid)
        if lab is None:
            continue
        c = centroids.get(int(lab))
        if c is None:
            continue
        v = vecs[i]
        sim = float(np.dot(v, c))
        dist = 1.0 - sim
        if dist > distance_threshold:
            out.append({"node_id": nid, "semantic_group": int(lab), "distance": float(dist)})
    out.sort(key=lambda x: -x["distance"])
    return out


def runtime_anomalies_payload(
    cfg: CFG,
    trace: dict[str, Any] | None,
    *,
    frequency_threshold: float = 0.05,
) -> dict[str, Any]:
    return {
        "rare_cfg_edges": rare_cfg_edges(cfg, trace, frequency_threshold=frequency_threshold),
        "definition": "frequency = edge_count / sum(all trace counts); flag if frequency < threshold",
    }
