"""Shared core types for mdengine generators (artifacts, telemetry schema)."""

from md_generator.core.artifacts.models import (
    ArtifactMetadata,
    ArtifactReference,
    ArtifactRelation,
    MarkdownArtifact,
)

__all__ = [
    "ArtifactMetadata",
    "ArtifactReference",
    "ArtifactRelation",
    "MarkdownArtifact",
]
