"""Pure Kafka EVENT edge specs (consumers + heuristic producers) for graph merge."""

from __future__ import annotations

import re
from dataclasses import dataclass

from md_generator.codeflow.models.ir import CallSite, EntryKind, FileParseResult


@dataclass(frozen=True, slots=True)
class EventEdgeSpec:
    """Directed EVENT edge to apply on the MultiDiGraph."""

    source: str
    target: str
    event_role: str  # consumer | producer
    confidence: float
    topic: str


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


def kafka_consumer_specs(parse_results: list[FileParseResult]) -> list[EventEdgeSpec]:
    """``topic:* → method`` for Java methods tagged as Kafka consumers."""
    out: list[EventEdgeSpec] = []
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
            for t in topics[:5]:
                tid = f"topic:{t}" if not str(t).startswith("topic:") else str(t)
                out.append(
                    EventEdgeSpec(
                        source=tid,
                        target=e.symbol_id,
                        event_role="consumer",
                        confidence=0.9,
                        topic=t,
                    ),
                )
    return out


_SEND_DQ = re.compile(r'\.send\s*\(\s*"([^"]+)"')
_SEND_SQ = re.compile(r"\.send\s*\(\s*'([^']+)'")
_PRODUCER_RECORD = re.compile(r"ProducerRecord\s*(?:<[^>]*>)?\s*\(\s*\"([^\"]+)\"")


def _caller_for_line(calls: list[CallSite], line: int) -> str | None:
    below = [(c.line, c.caller_id) for c in calls if c.line > 0 and c.line <= line]
    if not below:
        return None
    return max(below, key=lambda x: x[0])[1]


def _producer_topics_in_text(text: str) -> list[tuple[int, str]]:
    """(line_1_based, topic_name) for heuristic producer patterns."""
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if "send" not in line and "ProducerRecord" not in line:
            continue
        for pat in (_SEND_DQ, _SEND_SQ, _PRODUCER_RECORD):
            for m in pat.finditer(line):
                found.append((i, m.group(1)))
    return found


def kafka_producer_specs(parse_results: list[FileParseResult]) -> list[EventEdgeSpec]:
    """Heuristic ``method → topic:*`` when source looks like Kafka/Spring producers."""
    out: list[EventEdgeSpec] = []
    for pr in parse_results:
        if pr.language != "java":
            continue
        try:
            text = pr.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "Kafka" not in text and "kafka" not in text:
            continue
        hits = _producer_topics_in_text(text)
        if not hits:
            continue
        calls = pr.calls
        for line_no, topic in hits:
            tid = f"topic:{topic}"
            caller = _caller_for_line(calls, line_no)
            if not caller and pr.symbol_ids:
                caller = pr.symbol_ids[0]
            if not caller:
                continue
            out.append(
                EventEdgeSpec(
                    source=caller,
                    target=tid,
                    event_role="producer",
                    confidence=0.55,
                    topic=topic,
                ),
            )
    return out


def all_kafka_event_specs(parse_results: list[FileParseResult]) -> list[EventEdgeSpec]:
    return kafka_consumer_specs(parse_results) + kafka_producer_specs(parse_results)
