from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class LineKind(str, Enum):
    BLANK = "blank"
    NEW_LOG_LINE = "new_log_line"
    CONTINUATION = "continuation"
    STACKTRACE = "stacktrace"


@dataclass(slots=True)
class LogRecord:
    timestamp: datetime | None
    level: str
    logger: str | None
    thread: str | None
    message: str
    raw_message: str
    stacktrace: str | None
    source_file: Path
    line_number: int
    correlation_id: str | None = None
    fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParseResult:
    records: list[LogRecord]
    total_lines: int
    malformed_lines: int
    skipped_lines: int
    parse_duration_ms: int


@dataclass(slots=True)
class RunContext:
    input_paths: list[Path]
    output_dir: Path
    config: Any  # LogRunConfig — avoid circular import
    started_at: datetime
    records: list[LogRecord] = field(default_factory=list)
    parse_result: ParseResult | None = None
