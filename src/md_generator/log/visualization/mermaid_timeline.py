from __future__ import annotations

from datetime import datetime

from md_generator.log.parser.models import LogRecord


def _node_id(i: int) -> str:
    return f"E{i}"


def render_timeline_mermaid(records: list[LogRecord], *, max_nodes: int = 50) -> str:
    lines = ["```mermaid", "timeline", "    title Log timeline"]
    subset = records[:max_nodes]
    for i, r in enumerate(subset):
        ts = r.timestamp.isoformat() if isinstance(r.timestamp, datetime) else "unknown"
        label = (r.message or "")[:60].replace('"', "'")
        lines.append(f"    section {r.level or 'LOG'}")
        lines.append(f"        {_node_id(i)} : {ts} {label}")
    lines.append("```")
    return "\n".join(lines)
