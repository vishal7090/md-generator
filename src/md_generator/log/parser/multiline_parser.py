from __future__ import annotations

import re
import time
from collections.abc import Iterable
from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.parser.level_detector import message_without_level, scan_level
from md_generator.log.parser.logger_detector import refine_logger
from md_generator.log.parser.models import LogRecord, ParseResult
from md_generator.log.parser.regex_parser import compiled_pattern, try_structured_match
from md_generator.log.parser.stacktrace_parser import is_stacktrace_line
from md_generator.log.parser.timestamp_parser import parse_log_timestamp

_CORR_PATTERNS = (
    re.compile(r"\btraceId[=:]?\s*([\w-]+)", re.I),
    re.compile(r"\bspanId[=:]?\s*([\w-]+)", re.I),
    re.compile(r"\brequestId[=:]?\s*([\w-]+)", re.I),
    re.compile(r"\bcorrelation[_-]?id[=:]?\s*([\w-]+)", re.I),
)


def _extract_correlation(message: str) -> str | None:
    for rx in _CORR_PATTERNS:
        m = rx.search(message)
        if m:
            return m.group(1)
    return None


def _build_record(
    *,
    source_file: Path,
    start_line: int,
    ts_raw: str | None,
    level: str,
    logger: str | None,
    thread: str | None,
    message: str,
    stack: str | None,
    raw_lines: list[str],
    fuzzy_ts: bool,
) -> LogRecord:
    ts = parse_log_timestamp(ts_raw, fuzzy=fuzzy_ts)
    msg = message.strip()
    raw_msg = "\n".join(raw_lines).strip()
    corr = _extract_correlation(msg)
    return LogRecord(
        timestamp=ts,  # type: ignore[arg-type]
        level=level or "UNKNOWN",
        logger=refine_logger(logger),
        thread=thread.strip() if thread else None,
        message=msg,
        raw_message=raw_msg,
        stacktrace=stack.strip() if stack else None,
        source_file=source_file,
        line_number=start_line,
        correlation_id=corr,
        fingerprint=None,
        metadata={},
    )


def parse_file_lines(
    source_file: Path,
    cfg: LogRunConfig,
    lines: Iterable[tuple[int, str]],
) -> ParseResult:
    t0 = time.perf_counter()
    pattern = compiled_pattern(cfg.parser.line_regex)
    fuzzy = bool(cfg.parser.fuzzy_timestamp)

    records: list[LogRecord] = []
    total_lines = 0
    malformed = 0
    skipped = 0

    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        rec = _build_record(
            source_file=source_file,
            start_line=int(current["start_line"]),
            ts_raw=current.get("ts_raw"),
            level=str(current.get("level") or "UNKNOWN"),
            logger=current.get("logger"),
            thread=current.get("thread"),
            message=str(current.get("message") or ""),
            stack=current.get("stack"),
            raw_lines=list(current["raw_lines"]),
            fuzzy_ts=fuzzy,
        )
        records.append(rec)
        current = None

    for line_no, line in lines:
        total_lines += 1
        raw_line = line

        if not line.strip():
            if current:
                current["raw_lines"].append(raw_line)
                current["message"] = str(current["message"]) + "\n"
            else:
                skipped += 1
            continue

        structured = try_structured_match(line, pattern)
        is_new = structured is not None

        if not is_new and current is None:
            lvl = scan_level(line)
            if lvl:
                is_new = True
                structured = {
                    "timestamp": "",
                    "level": lvl,
                    "message": message_without_level(line),
                }

        if is_new and structured is not None:
            flush()
            msg = structured.get("message") or ""
            current = {
                "start_line": line_no,
                "ts_raw": structured.get("timestamp") or None,
                "level": (structured.get("level") or "INFO").upper(),
                "logger": structured.get("logger"),
                "thread": structured.get("thread"),
                "message": msg,
                "stack": None,
                "raw_lines": [raw_line],
            }
            if current["level"] == "WARNING":
                current["level"] = "WARN"
            continue

        if current is None:
            malformed += 1
            continue

        current["raw_lines"].append(raw_line)
        if is_stacktrace_line(line):
            prev = current.get("stack")
            current["stack"] = (prev + "\n" + line).strip() if prev else line
        else:
            current["message"] = str(current["message"]) + "\n" + line

    flush()
    ms = int((time.perf_counter() - t0) * 1000)
    return ParseResult(
        records=records,
        total_lines=total_lines,
        malformed_lines=malformed,
        skipped_lines=skipped,
        parse_duration_ms=ms,
    )
