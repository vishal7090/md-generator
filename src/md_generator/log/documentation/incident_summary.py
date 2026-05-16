from __future__ import annotations

from pathlib import Path

from md_generator.log.incidents.models import Incident
from md_generator.log.utils.io import write_text


def write_incident_summaries(out: Path, incidents: list[Incident]) -> None:
    doc_dir = out / "documentation" / "incidents"
    doc_dir.mkdir(parents=True, exist_ok=True)
    for i, inc in enumerate(incidents[:200], start=1):
        body = (
            f"# {inc.title}\n\n"
            f"Occurrences: {len(inc.occurrences)}\n\n"
            f"Severity: {inc.severity}\n\n"
            f"Services: {', '.join(inc.affected_services) or 'n/a'}\n"
        )
        write_text(doc_dir / f"summary_{i:03d}.md", body)
