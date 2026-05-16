from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from md_generator.log.parser.models import LogRecord


def score_log_trace_link(
    record: LogRecord,
    span: dict[str, Any],
    *,
    window_seconds: int = 300,
) -> float:
    score = 0.5
    tid_r = str((record.metadata or {}).get("traceId") or (record.metadata or {}).get("trace_id") or "")
    tid_s = str(span.get("traceId") or span.get("trace_id") or "")
    if tid_r and tid_s and tid_r == tid_s:
        score += 0.4
    ts_r = record.timestamp
    ts_s = span.get("startTime") or span.get("start_time")
    if isinstance(ts_r, datetime) and ts_s:
        try:
            if isinstance(ts_s, (int, float)):
                ts_span = datetime.fromtimestamp(ts_s / 1e9 if ts_s > 1e12 else ts_s)
            else:
                ts_span = datetime.fromisoformat(str(ts_s).replace("Z", "+00:00"))
            delta = abs((ts_r - ts_span.replace(tzinfo=None)).total_seconds())
            if delta <= window_seconds:
                score += 0.1 * (1.0 - delta / window_seconds)
        except (TypeError, ValueError):
            pass
    return min(1.0, score)
