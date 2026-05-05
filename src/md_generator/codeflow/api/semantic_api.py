"""Pure helpers for semantic similarity (used by CLI / scan / future HTTP)."""

from __future__ import annotations

from typing import Any

from md_generator.codeflow.graph.embeddings import embed_texts
from md_generator.codeflow.graph.semantic_enricher import SemanticArtifacts


def neighbors_for_node(artifacts: SemanticArtifacts, node_id: str, top_k: int) -> list[tuple[str, float]]:
    v = artifacts.index.vector_for(node_id)
    if v is None:
        return []
    return artifacts.index.search(v, top_k, exclude={node_id})


def neighbors_serializable(
    artifacts: SemanticArtifacts,
    node_id: str,
    top_k: int,
    graph: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for nid, score in neighbors_for_node(artifacts, node_id, top_k):
        d = dict(graph.nodes[nid]) if nid in graph else {}
        rows.append(
            {
                "node_id": nid,
                "score": score,
                "name": d.get("method_name"),
                "class_name": d.get("class_name"),
                "file_path": d.get("file_path"),
            },
        )
    return rows


def search_similar(
    artifacts: SemanticArtifacts,
    query_text: str,
    top_k: int,
    *,
    model_id: str | None = None,
) -> list[tuple[str, float]]:
    mid = model_id or artifacts.model_id
    qv = embed_texts([query_text], mid, normalize_embeddings=True)[0]
    return artifacts.index.search(qv, top_k, exclude=None)


def search_similar_serializable(
    artifacts: SemanticArtifacts,
    query_text: str,
    top_k: int,
    graph: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for nid, score in search_similar(artifacts, query_text, top_k):
        d = dict(graph.nodes[nid]) if nid in graph else {}
        rows.append(
            {
                "node_id": nid,
                "score": score,
                "name": d.get("method_name"),
                "class_name": d.get("class_name"),
                "file_path": d.get("file_path"),
            },
        )
    return rows
