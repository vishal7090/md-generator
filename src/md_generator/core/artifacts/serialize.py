from __future__ import annotations

from typing import Any

from md_generator.core.artifacts.models import ArtifactMetadata, ArtifactRelation, MarkdownArtifact


def artifact_to_dict(art: MarkdownArtifact) -> dict[str, Any]:
    md = art.metadata
    return {
        "artifact_id": art.artifact_id,
        "artifact_type": art.artifact_type,
        "title": art.title,
        "content": art.content,
        "source_refs": list(art.source_refs),
        "tags": list(art.tags),
        "metadata": {
            "severity": md.severity,
            "service": md.service,
            "chunk_id": md.chunk_id,
            "tags": list(md.tags),
            "agent_hints": dict(md.agent_hints),
            "lineage": dict(md.lineage),
            "extra": dict(md.extra),
        },
        "relations": [
            {"target_id": r.target_id, "relation_type": r.relation_type} for r in art.relations
        ],
    }


def artifact_from_dict(data: dict[str, Any]) -> MarkdownArtifact:
    md_raw = data.get("metadata") or {}
    if not isinstance(md_raw, dict):
        md_raw = {}
    md = ArtifactMetadata(
        severity=md_raw.get("severity"),
        service=md_raw.get("service"),
        chunk_id=md_raw.get("chunk_id"),
        tags=list(md_raw.get("tags") or []),
        agent_hints=dict(md_raw.get("agent_hints") or {}),
        lineage=dict(md_raw.get("lineage") or {}),
        extra={k: v for k, v in md_raw.items() if k not in {"severity", "service", "chunk_id", "tags", "agent_hints", "lineage"}},
    )
    rels = [
        ArtifactRelation(target_id=str(r["target_id"]), relation_type=str(r["relation_type"]))
        for r in (data.get("relations") or [])
        if isinstance(r, dict) and "target_id" in r
    ]
    return MarkdownArtifact(
        artifact_id=str(data["artifact_id"]),
        artifact_type=str(data.get("artifact_type", "unknown")),
        title=str(data.get("title", "")),
        content=str(data.get("content", "")),
        metadata=md,
        source_refs=[str(x) for x in (data.get("source_refs") or [])],
        tags=[str(x) for x in (data.get("tags") or [])],
        relations=rels,
    )
