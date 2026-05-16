from __future__ import annotations

import re

from md_generator.log.knowledge_graph.graph_models import GraphEdge, GraphNode
from md_generator.log.parser.models import LogRecord

_REDIS = re.compile(r"\bredis\b", re.I)
_PG = re.compile(r"\bpostgres|postgresql\b", re.I)
_KAFKA = re.compile(r"\bkafka\b", re.I)


def extract_edges(records: list[LogRecord]) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: dict[str, GraphNode] = {}
    edges: set[tuple[str, str, str]] = set()
    for r in records:
        svc = (r.logger or "service").strip() or "service"
        sid = f"svc:{svc}"
        nodes[sid] = GraphNode(node_id=sid, label=svc, kind="service")
        msg = r.message.lower()
        if _REDIS.search(msg):
            tid = "dep:redis"
            nodes[tid] = GraphNode(node_id=tid, label="Redis", kind="datastore")
            edges.add((sid, tid, "uses"))
        if _PG.search(msg):
            tid = "dep:postgresql"
            nodes[tid] = GraphNode(node_id=tid, label="PostgreSQL", kind="datastore")
            edges.add((sid, tid, "uses"))
        if _KAFKA.search(msg):
            tid = "dep:kafka"
            nodes[tid] = GraphNode(node_id=tid, label="Kafka", kind="messaging")
            edges.add((sid, tid, "publishes"))
    edge_objs = [GraphEdge(source_id=s, target_id=t, relation=rel) for s, t, rel in sorted(edges)]
    return list(nodes.values()), edge_objs
