from __future__ import annotations

from md_generator.log.knowledge_graph.graph_models import GraphEdge, GraphNode
from md_generator.log.knowledge_graph.relation_extractor import extract_edges
from md_generator.log.parser.models import LogRecord


def build_graph(records: list[LogRecord]) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes, edges = extract_edges(records)
    seen: set[tuple[str, str, str]] = set()
    deduped: list[GraphEdge] = []
    for e in edges:
        key = (e.source_id, e.target_id, e.relation)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    return nodes, deduped
