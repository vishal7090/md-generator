from __future__ import annotations

from md_generator.log.parser.models import LogRecord


def render_sequence_mermaid(records: list[LogRecord], *, max_messages: int = 30) -> str:
    lines = ["```mermaid", "sequenceDiagram"]
    participants: dict[str, str] = {}
    for r in records[:max_messages]:
        svc = str((r.metadata or {}).get("service") or r.logger or "app")
        if svc not in participants:
            pid = f"P{len(participants)}"
            participants[svc] = pid
            lines.append(f"    participant {pid} as {svc}")
    for r in records[:max_messages]:
        svc = str((r.metadata or {}).get("service") or r.logger or "app")
        pid = participants[svc]
        msg = (r.message or "")[:40].replace('"', "'")
        lines.append(f"    {pid}->>{pid}: {r.level} {msg}")
    lines.append("```")
    return "\n".join(lines)
