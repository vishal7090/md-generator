from __future__ import annotations

from pathlib import Path

from md_generator.log.incidents.incident_engine import build_incidents
from md_generator.log.incidents.models import Incident
from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def _format_ts(ts: object | None) -> str:
    if ts is None:
        return "n/a"
    return str(ts)


def render_incident_markdown(inc: Incident, *, index: int) -> str:
    lines = [
        f"# Incident: {inc.title}",
        "",
        "## Summary",
        f"- Occurrences: {len(inc.occurrences)}",
        f"- Severity: {inc.severity}",
        f"- First Seen: {_format_ts(inc.first_seen)}",
        f"- Last Seen: {_format_ts(inc.last_seen)}",
        f"- Incident ID: `{inc.incident_id}`",
        "",
        "## Representative Messages",
        "",
    ]
    for m in inc.representative_messages:
        lines.append(f"- {m}")
    if not inc.representative_messages:
        lines.append("_None_")
    lines.extend(["", "## Related Stacktraces", ""])
    for st in inc.stacktraces:
        lines.append("```")
        lines.append(st)
        lines.append("```")
        lines.append("")
    if not inc.stacktraces:
        lines.append("_None_")
    lines.extend(["", "## Affected Services", ""])
    for svc in inc.affected_services:
        lines.append(f"- `{svc}`")
    if not inc.affected_services:
        lines.append("_None_")
    lines.append("")
    return "\n".join(lines)


def write_incidents(root: Path, records: list[LogRecord], cfg: object) -> list[Incident]:
    from md_generator.log.config.schemas import LogRunConfig

    assert isinstance(cfg, LogRunConfig)
    incidents = build_incidents(records, cfg)
    for i, inc in enumerate(incidents[:500], start=1):
        body = render_incident_markdown(inc, index=i)
        write_text(root / "incidents" / f"incident_{i:03d}.md", body)
    return incidents
