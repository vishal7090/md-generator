from __future__ import annotations

from md_generator.log.parser.models import LogRecord


def render_topology_mermaid(records: list[LogRecord]) -> str:
    services: set[str] = set()
    edges: set[tuple[str, str]] = set()
    for r in records:
        svc = (r.metadata or {}).get("service") or r.logger or "unknown"
        services.add(str(svc))
        host = (r.metadata or {}).get("host")
        if host:
            edges.add((str(host), str(svc)))
    lines = ["```mermaid", "flowchart LR"]
    for s in sorted(services):
        sid = s.replace("-", "_").replace(".", "_")
        lines.append(f"    {sid}[{s}]")
    for a, b in sorted(edges):
        aid = a.replace("-", "_")
        bid = b.replace("-", "_")
        lines.append(f"    {aid} --> {bid}")
    lines.append("```")
    return "\n".join(lines)
