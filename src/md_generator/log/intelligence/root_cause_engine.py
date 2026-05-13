from __future__ import annotations

import json
from pathlib import Path

from md_generator.log.incidents.models import Incident
from md_generator.log.intelligence.dependency_analysis import dependency_failure_hint
from md_generator.log.intelligence.heuristics import score_timeout_pool
from md_generator.log.utils.io import write_text


def analyze_root_causes(incidents: list[Incident]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for inc in incidents:
        dep = dependency_failure_hint(inc)
        pool = score_timeout_pool(inc)
        likely = None
        evidence: list[str] = []
        if pool >= 50:
            likely = "connection pool exhaustion"
            evidence.append("timeout + connection/pool signals")
        elif dep:
            likely = dep
            evidence.append("dependency keyword match")
        if likely:
            out.append(
                {
                    "incident": inc.title,
                    "incident_id": inc.incident_id,
                    "likely_root_cause": likely,
                    "score": pool,
                    "evidence": evidence,
                },
            )
    return out


def write_root_cause_artifacts(root: Path, incidents: list[Incident]) -> None:
    results = analyze_root_causes(incidents)
    write_text(root / "intelligence" / "root_causes.json", json.dumps(results, indent=2) + "\n")
    lines = ["# Root cause analysis", ""]
    for row in results:
        lines.append(f"## {row['incident']}")
        lines.append(f"- Likely root cause: {row['likely_root_cause']}")
        lines.append(f"- Evidence: {', '.join(row['evidence'])}")  # type: ignore[arg-type]
        lines.append("")
    write_text(root / "intelligence" / "summary.md", "\n".join(lines))
