"""Emit EVENT edges (Kafka consumer → topic) onto a ``MultiDiGraph``."""

from __future__ import annotations

import re

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, edge_payload
from md_generator.codeflow.models.ir import EntryKind, FileParseResult


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


def _kafka_topics_from_java_source(text: str) -> list[str]:
    topics: list[str] = []
    for m in re.finditer(r"@KafkaListener\s*\(([^)]*)\)", text, re.DOTALL):
        inner = m.group(1)
        for tm in re.finditer(r"topics\s*=\s*\{([^}]*)\}", inner):
            for q in re.findall(r'"([^"]+)"', tm.group(1)):
                topics.append(q)
        for sm in re.finditer(r'topics\s*=\s*"([^"]+)"', inner):
            topics.append(sm.group(1))
    return topics


def apply_event_edges(g: CodeflowGraph, parse_results: list[FileParseResult]) -> None:
    """Add ``topic:{name}`` nodes and EVENT edges ``topic → consumer`` for Java Kafka listeners."""
    for pr in parse_results:
        if pr.language != "java":
            continue
        kafka_entries = [e for e in pr.entries if e.kind == EntryKind.KAFKA]
        if not kafka_entries:
            continue
        try:
            text = pr.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        topics = _kafka_topics_from_java_source(text)
        if not topics:
            topics = ["unknown"]
        for e in kafka_entries:
            sym = e.symbol_id
            if not g.has_node(sym):
                continue
            tags = list(g.nodes[sym].get("tags") or [])
            for t in ("event", "consumer"):
                if t not in tags:
                    tags.append(t)
            g.nodes[sym]["tags"] = tags
            for t in topics[:5]:
                tid = f"topic:{t}"
                _ensure_topic_node(g, tid, pr.language)
                g.add_edge(
                    tid,
                    sym,
                    **edge_payload(
                        relation=rel.REL_EVENT,
                        condition=None,
                        confidence=0.9,
                        type="event",
                        event_role="consumer",
                    ),
                )
