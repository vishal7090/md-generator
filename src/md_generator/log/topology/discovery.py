from __future__ import annotations

import re
from dataclasses import dataclass, field

from md_generator.log.parser.models import LogRecord

_EDGE_PATTERNS = [
    re.compile(r"\b(?:http|https)://([^\s/]+)", re.I),
    re.compile(r"\b(?:redis|kafka|postgres|mysql)://([^\s/]+)", re.I),
    re.compile(r"\bconnected to ([a-z0-9._-]+)", re.I),
]


@dataclass(slots=True)
class TopologyEdge:
    source: str
    target: str
    edge_type: str


@dataclass(slots=True)
class TopologyGraph:
    nodes: set[str] = field(default_factory=set)
    edges: list[TopologyEdge] = field(default_factory=list)


def discover_topology(records: list[LogRecord]) -> TopologyGraph:
    g = TopologyGraph()
    for r in records:
        src = str((r.metadata or {}).get("service") or r.logger or "app")
        g.nodes.add(src)
        msg = r.message or ""
        for pat in _EDGE_PATTERNS:
            for m in pat.finditer(msg):
                tgt = m.group(1)
                g.nodes.add(tgt)
                g.edges.append(TopologyEdge(source=src, target=tgt, edge_type="depends_on"))
    return g


def topology_to_mermaid(g: TopologyGraph) -> str:
    lines = ["```mermaid", "flowchart TB"]
    seen_edges: set[tuple[str, str]] = set()
    for n in sorted(g.nodes):
        nid = n.replace("-", "_").replace(".", "_")[:40]
        lines.append(f"    {nid}[{n[:40]}]")
    for e in g.edges:
        key = (e.source, e.target)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        a = e.source.replace("-", "_")[:40]
        b = e.target.replace("-", "_")[:40]
        lines.append(f"    {a} --> {b}")
    lines.append("```")
    return "\n".join(lines)
