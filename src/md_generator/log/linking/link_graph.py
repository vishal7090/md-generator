from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from md_generator.log.incidents.models import Incident
from md_generator.log.parser.models import LogRecord


@dataclass(slots=True)
class LinkNode:
    node_id: str
    node_type: str
    label: str


@dataclass(slots=True)
class LinkEdge:
    source: str
    target: str
    edge_type: str


@dataclass(slots=True)
class LinkGraph:
    nodes: list[LinkNode] = field(default_factory=list)
    edges: list[LinkEdge] = field(default_factory=list)


def build_link_graph(records: list[LogRecord], incidents: list[Incident]) -> LinkGraph:
    g = LinkGraph()
    services: set[str] = set()
    for r in records:
        svc = str((r.metadata or {}).get("service") or r.logger or "")
        if svc:
            services.add(svc)
            nid = f"service://{svc}"
            g.nodes.append(LinkNode(nid, "service", svc))
    for inc in incidents:
        iid = f"incident://{inc.incident_id}"
        g.nodes.append(LinkNode(iid, "incident", inc.title))
        for svc in inc.affected_services:
            g.edges.append(LinkEdge(iid, f"service://{svc}", "affects"))
    seen: set[tuple[str, str, str]] = set()
    deduped: list[LinkEdge] = []
    for e in g.edges:
        key = (e.source, e.target, e.edge_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    g.edges = deduped
    return g


def write_link_index(out: Path, graph: LinkGraph) -> None:
    payload = {
        "nodes": [{"id": n.node_id, "type": n.node_type, "label": n.label} for n in graph.nodes],
        "edges": [{"source": e.source, "target": e.target, "type": e.edge_type} for e in graph.edges],
    }
    (out / "link_index.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
