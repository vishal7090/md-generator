from __future__ import annotations

from collections import defaultdict

from md_generator.log.correlation.correlation_models import CorrelatedRequest, TraceLink
from md_generator.log.correlation.request_parser import parse_request_fields
from md_generator.log.correlation.session_parser import parse_session_id
from md_generator.log.correlation.trace_parser import parse_trace_fields
from md_generator.log.parser.models import LogRecord


def build_correlated_requests(records: list[LogRecord]) -> list[CorrelatedRequest]:
    buckets: dict[str, list[LogRecord]] = defaultdict(list)
    for r in records:
        text = r.message + " " + (r.stacktrace or "")
        rid, cid = parse_request_fields(text)
        key = rid or r.correlation_id or cid
        if not key:
            continue
        buckets[key].append(r)
    out: list[CorrelatedRequest] = []
    for rid, rs in buckets.items():
        text = rs[0].message
        _, cid = parse_request_fields(text)
        sid = parse_session_id(text)
        out.append(
            CorrelatedRequest(
                request_id=rid,
                correlation_id=cid or rs[0].correlation_id,
                session_id=sid,
                records=sorted(rs, key=lambda x: (x.timestamp or x.line_number, x.line_number)),
            ),
        )
    out.sort(key=lambda x: (x.first_seen or x.request_id))
    return out


def build_trace_links(records: list[LogRecord]) -> list[TraceLink]:
    buckets: dict[str, list[LogRecord]] = defaultdict(list)
    spans: dict[str, str | None] = {}
    for r in records:
        text = r.message + " " + (r.stacktrace or "")
        tid, sid = parse_trace_fields(text)
        if not tid:
            continue
        buckets[tid].append(r)
        spans[tid] = sid
    return [
        TraceLink(trace_id=tid, span_id=spans.get(tid), records=rs)
        for tid, rs in sorted(buckets.items())
    ]
