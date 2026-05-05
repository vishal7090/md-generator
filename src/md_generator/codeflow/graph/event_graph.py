"""Emit EVENT edges (Kafka producer/consumer ↔ topic) onto a ``MultiDiGraph``."""

from __future__ import annotations

from md_generator.codeflow.detectors.event_detector import all_kafka_event_specs
from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, edge_payload
from md_generator.codeflow.models.ir import FileParseResult


def _ensure_topic_node(g: CodeflowGraph, topic_id: str, language: str) -> None:
    if g.has_node(topic_id):
        return
    tname = topic_id[6:] if topic_id.startswith("topic:") else topic_id
    nid = topic_id if topic_id.startswith("topic:") else f"topic:{topic_id}"
    g.add_node(
        nid,
        id=nid,
        type="topic",
        kind="Topic",
        name=tname,
        class_name=None,
        method_name=None,
        file_path="",
        language=language,
        tags=["event", "topic"],
    )


def apply_event_edges(g: CodeflowGraph, parse_results: list[FileParseResult]) -> None:
    """Add ``topic:{name}`` nodes and EVENT edges (consumer: topic→method, producer: method→topic)."""
    for spec in all_kafka_event_specs(parse_results):
        topic_id = spec.source if spec.event_role == "consumer" else spec.target
        method_id = spec.target if spec.event_role == "consumer" else spec.source
        _ensure_topic_node(g, topic_id, "java")
        if not g.has_node(method_id):
            continue
        tags = list(g.nodes[method_id].get("tags") or [])
        role_tag = "consumer" if spec.event_role == "consumer" else "producer"
        for t in ("event", role_tag):
            if t not in tags:
                tags.append(t)
        g.nodes[method_id]["tags"] = tags
        u, v = spec.source, spec.target
        g.add_edge(
            u,
            v,
            **edge_payload(
                relation=rel.REL_EVENT,
                condition=None,
                confidence=spec.confidence,
                type="event",
                event_role=spec.event_role,
            ),
        )
