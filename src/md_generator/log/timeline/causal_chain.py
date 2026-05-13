from __future__ import annotations

from md_generator.log.timeline.ordering import order_events
from md_generator.log.timeline.timeline_models import TimelineEvent


def infer_causal_chain(events: list[TimelineEvent], window_seconds: int) -> list[str]:
    chain: list[str] = []
    keywords = ("latency", "timeout", "failed", "error", "refused")
    for ev in events:
        low = ev.label.lower()
        if any(k in low for k in keywords):
            ts = ev.timestamp.isoformat() if ev.timestamp else f"line {ev.record.line_number}"
            chain.append(f"{ts} -> {ev.label[:120]}")
    return chain[:50]
