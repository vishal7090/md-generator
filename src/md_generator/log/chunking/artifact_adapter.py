from __future__ import annotations

from md_generator.core.artifacts.models import ArtifactMetadata, MarkdownArtifact
from md_generator.log.chunking.chunk_models import SemanticChunk


def semantic_chunk_to_artifact(ch: SemanticChunk) -> MarkdownArtifact:
    md = dict(ch.metadata)
    return MarkdownArtifact(
        artifact_id=ch.chunk_id,
        artifact_type=ch.chunk_type,
        title=ch.title,
        content=ch.content,
        metadata=ArtifactMetadata(
            chunk_id=ch.chunk_id,
            tags=list(md.pop("tags", [])) if isinstance(md.get("tags"), list) else [],
            extra=md,
        ),
        source_refs=list(ch.source_refs),
    )
