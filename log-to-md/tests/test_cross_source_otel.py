from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from md_generator.log.correlation.cross_source import correlate_cross_source, render_cross_source_markdown
from md_generator.log.parser.models import LogRecord


def test_cross_source_links_log_to_span() -> None:
    otel_dir = Path(__file__).resolve().parent / "fixtures" / "otel"
    records = [
        LogRecord(
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            level="ERROR",
            logger="checkout",
            thread=None,
            message="payment failed",
            raw_message="payment failed",
            stacktrace=None,
            source_file=Path("app.log"),
            line_number=1,
            metadata={"traceId": "4bf92f3577b34da6a3ce929d0e0e4736"},
        ),
    ]
    result = correlate_cross_source(records, otel_dir, window_seconds=300)
    assert len(result.links) >= 1
    md = render_cross_source_markdown(result)
    assert "4bf92f3577b34da6a3ce929d0e0e4736" in md
