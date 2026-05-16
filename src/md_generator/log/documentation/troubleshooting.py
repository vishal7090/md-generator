from __future__ import annotations

from pathlib import Path

from md_generator.log.incidents.models import Incident
from md_generator.log.utils.io import write_text


def write_troubleshooting_guides(out: Path, incidents: list[Incident]) -> None:
    doc_dir = out / "documentation" / "troubleshooting"
    doc_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Troubleshooting index", ""]
    for inc in incidents[:100]:
        lines.append(f"- **{inc.title}** — {len(inc.occurrences)} occurrences, severity {inc.severity}")
    write_text(doc_dir / "README.md", "\n".join(lines) + "\n")
