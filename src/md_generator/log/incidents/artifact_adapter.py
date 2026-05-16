from __future__ import annotations

from md_generator.core.artifacts.models import ArtifactMetadata, MarkdownArtifact
from md_generator.log.incidents.models import Incident


def incident_to_artifact(inc: Incident, *, index: int) -> MarkdownArtifact:
    body = "\n".join(f"- {m}" for m in inc.representative_messages)
    return MarkdownArtifact(
        artifact_id=f"incident://{inc.incident_id}",
        artifact_type="incident",
        title=inc.title,
        content=body,
        metadata=ArtifactMetadata(
            severity=str(inc.severity),
            service=inc.affected_services[0] if inc.affected_services else None,
            chunk_id=f"incident_{index:03d}",
            tags=["incident"],
            agent_hints={
                "searchable": True,
                "summarize": True,
                "root_cause_candidate": inc.severity >= 5.0,
            },
            extra={"occurrences": len(inc.occurrences), "fingerprint": inc.fingerprint},
        ),
        source_refs=[inc.incident_id],
    )
