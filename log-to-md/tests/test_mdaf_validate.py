from __future__ import annotations

from md_generator.core.artifacts.mdaf_validate import validate_artifact_dict, validate_frontmatter_keys
from md_generator.core.artifacts.models import ArtifactMetadata, MarkdownArtifact
from md_generator.core.artifacts.serialize import artifact_from_dict, artifact_to_dict
from md_generator.log.writers.frontmatter_writer import render_frontmatter


def test_artifact_round_trip() -> None:
    art = MarkdownArtifact(
        artifact_id="chunk://ns/incident/foo/001",
        artifact_type="incident",
        title="Test",
        content="body",
        metadata=ArtifactMetadata(service="api", tags=["error"]),
    )
    d = artifact_to_dict(art)
    assert not validate_artifact_dict(d)
    restored = artifact_from_dict(d)
    assert restored.artifact_id == art.artifact_id


def test_frontmatter_keys() -> None:
    fm = render_frontmatter({"artifact_id": "x", "artifact_type": "incident", "service": "api"})
    assert fm.startswith("---")
    assert not validate_frontmatter_keys({"artifact_id", "artifact_type", "service"})
