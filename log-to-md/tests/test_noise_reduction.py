from __future__ import annotations

from datetime import datetime
from pathlib import Path

from md_generator.log.config.schemas import NoiseReductionSection
from md_generator.log.noise_reduction.filter import apply_noise_filters
from md_generator.log.parser.models import LogRecord


def _rec(msg: str) -> LogRecord:
    return LogRecord(
        timestamp=datetime(2024, 1, 1),
        level="ERROR",
        logger="app",
        thread=None,
        message=msg,
        raw_message=msg,
        stacktrace=None,
        source_file=Path("a.log"),
        line_number=1,
    )


def test_dedupe_filters_duplicates() -> None:
    section = NoiseReductionSection(enabled=True, dedupe=True, entropy_threshold=0.0)
    records = [_rec("same"), _rec("same"), _rec("other message here")]
    out = apply_noise_filters(records, section)
    assert len(out) == 2
