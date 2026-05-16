from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from md_generator.log.correlation.correlation_scoring import score_log_trace_link
from md_generator.log.parser.models import LogRecord


@dataclass(slots=True)
class CrossSourceLink:
    log_record_index: int
    trace_id: str
    score: float
    incident_id: str | None = None


@dataclass(slots=True)
class CrossSourceResult:
    links: list[CrossSourceLink] = field(default_factory=list)


def _load_otel_spans(otel_dir: Path) -> list[dict]:
    spans: list[dict] = []
    if not otel_dir.is_dir():
        return spans
    for p in sorted(otel_dir.rglob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                spans.extend(data)
            elif isinstance(data, dict) and "spans" in data:
                spans.extend(data["spans"])
        except (json.JSONDecodeError, OSError):
            continue
    return spans


def correlate_cross_source(
    records: list[LogRecord],
    otel_path: Path | None,
    *,
    window_seconds: int = 300,
) -> CrossSourceResult:
    result = CrossSourceResult()
    spans = _load_otel_spans(otel_path) if otel_path else []
    span_by_trace: dict[str, list[dict]] = {}
    for sp in spans:
        tid = str(sp.get("traceId") or sp.get("trace_id") or "")
        if tid:
            span_by_trace.setdefault(tid, []).append(sp)
    for i, r in enumerate(records):
        md = r.metadata or {}
        tid = str(md.get("traceId") or md.get("trace_id") or "")
        if not tid or tid not in span_by_trace:
            continue
        sp = span_by_trace[tid][0]
        score = score_log_trace_link(r, sp, window_seconds=window_seconds)
        result.links.append(CrossSourceLink(log_record_index=i, trace_id=tid, score=score))
    return result


def render_cross_source_markdown(result: CrossSourceResult) -> str:
    lines = ["# Cross-source correlation", ""]
    for link in sorted(result.links, key=lambda x: -x.score)[:100]:
        lines.append(f"- record #{link.log_record_index} ↔ trace `{link.trace_id}` (score {link.score:.2f})")
    return "\n".join(lines) + "\n"
