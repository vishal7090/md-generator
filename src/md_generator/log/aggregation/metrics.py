from __future__ import annotations

from dataclasses import dataclass

from md_generator.log.parser.models import LogRecord


@dataclass
class RunMetrics:
    files_parsed: int = 0
    lines_total: int = 0
    records_total: int = 0
    malformed_lines: int = 0
    skipped_lines: int = 0
    parse_duration_ms: int = 0
    lines_per_sec: float = 0.0

    def merge_parse(self, *, lines: int, malformed: int, skipped: int, duration_ms: int) -> None:
        self.lines_total += lines
        self.malformed_lines += malformed
        self.skipped_lines += skipped
        self.parse_duration_ms += duration_ms
        if duration_ms > 0:
            self.lines_per_sec = self.lines_total / (duration_ms / 1000.0)

    def add_records(self, n: int) -> None:
        self.records_total += n


def summarize_records(records: list[LogRecord]) -> dict[str, float | int]:
    return {
        "records": len(records),
        "error_rate": sum(1 for r in records if r.level.upper() in {"ERROR", "FATAL"}) / max(len(records), 1),
    }
