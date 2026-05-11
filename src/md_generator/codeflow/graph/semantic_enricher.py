"""Build embedding matrix, KMeans labels, and ``SemanticIndex`` for a scan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pathlib import Path

from md_generator.codeflow.core.cache_manager import write_json_cache
from md_generator.codeflow.graph.clustering import semantic_clusters_from_embeddings
from md_generator.codeflow.graph.embeddings import build_embedding_text, embed_nodes_cached
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph
from md_generator.codeflow.graph.semantic_index import SemanticIndex


@dataclass
class SemanticArtifacts:
    model_id: str
    node_ids: list[str]
    vectors: Any  # np.ndarray float32
    labels: dict[str, int]
    index: SemanticIndex


def _select_embed_nodes(g: CodeflowGraph, max_nodes: int) -> list[str]:
    cands: list[str] = []
    for n, d in g.nodes(data=True):
        if not isinstance(n, str) or "::" not in n:
            continue
        if n.startswith("unknown::") or n.startswith("topic:") or n.startswith("file:"):
            continue
        t = d.get("type")
        if t not in ("method", "entry"):
            continue
        cands.append(n)
    cands = sorted(set(cands))
    return cands[:max_nodes]


def build_semantic_artifacts(
    g: CodeflowGraph,
    project_root: Any,
    *,
    model_id: str,
    max_nodes: int,
    k_semantic: int,
    encode_fn: Callable[[list[str], str], Any] | None = None,
) -> SemanticArtifacts | None:
    node_ids = _select_embed_nodes(g, max_nodes)
    if len(node_ids) < 2:
        return None
    texts = [build_embedding_text(g, nid) or nid for nid in node_ids]
    if not any(t.strip() for t in texts):
        return None
    vectors = embed_nodes_cached(project_root, model_id, node_ids, texts, encode_fn=encode_fn)
    try:
        write_json_cache(
            Path(project_root),
            "semantic_meta",
            model_id,
            {
                "model_id": model_id,
                "backend": "custom" if encode_fn is not None else "local",
                "embedded_count": len(node_ids),
            },
            ttl_seconds=0,
        )
    except OSError:
        pass
    import numpy as np

    vectors = np.asarray(vectors, dtype=np.float32)
    try:
        labs = semantic_clusters_from_embeddings(vectors.tolist(), k=k_semantic)
    except ImportError:
        return None
    labels = {nid: int(labs[i]) for i, nid in enumerate(node_ids) if i < len(labs)}
    index = SemanticIndex()
    index.build(node_ids, vectors)
    return SemanticArtifacts(
        model_id=model_id,
        node_ids=node_ids,
        vectors=vectors,
        labels=labels,
        index=index,
    )


def attach_semantic_groups(g: CodeflowGraph, labels: dict[str, int]) -> None:
    for nid, lab in labels.items():
        if nid in g:
            g.nodes[nid]["semantic_group"] = int(lab)
