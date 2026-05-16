from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ArtifactReference:
    ref_type: str
    ref_id: str


@dataclass(slots=True)
class ArtifactRelation:
    target_id: str
    relation_type: str


@dataclass(slots=True)
class ArtifactMetadata:
    severity: str | None = None
    service: str | None = None
    chunk_id: str | None = None
    tags: list[str] = field(default_factory=list)
    agent_hints: dict[str, bool] = field(default_factory=dict)
    lineage: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MarkdownArtifact:
    artifact_id: str
    artifact_type: str
    title: str
    content: str
    metadata: ArtifactMetadata = field(default_factory=ArtifactMetadata)
    source_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    relations: list[ArtifactRelation] = field(default_factory=list)

    def to_frontmatter_dict(self) -> dict[str, Any]:
        md = self.metadata
        out: dict[str, Any] = {
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
        }
        if md.severity:
            out["severity"] = md.severity
        if md.service:
            out["service"] = md.service
        if md.chunk_id:
            out["chunk_id"] = md.chunk_id
        if md.tags or self.tags:
            out["tags"] = sorted(set(md.tags) | set(self.tags))
        if md.agent_hints:
            out["agent_hints"] = dict(sorted(md.agent_hints.items()))
        if md.lineage:
            out["lineage"] = md.lineage
        out.update(md.extra)
        return out
