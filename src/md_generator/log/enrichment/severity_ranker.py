from __future__ import annotations

from dataclasses import replace

from md_generator.log.parser.models import LogRecord

_ORDER = {"FATAL": 60, "ERROR": 50, "WARN": 40, "WARNING": 40, "INFO": 30, "DEBUG": 20, "TRACE": 10}


def add_severity_rank(record: LogRecord) -> LogRecord:
    rank = _ORDER.get(record.level.upper(), 25)
    md = dict(record.metadata)
    md["severity_rank"] = rank
    return replace(record, metadata=md)
