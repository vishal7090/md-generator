from __future__ import annotations

from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.parser.multiline_parser import parse_file_lines


def _cfg() -> LogRunConfig:
    return LogRunConfig().normalized()


def test_stacktrace_attaches_to_previous_record() -> None:
    lines = [
        (1, "2024-01-15T10:00:00Z INFO ok"),
        (2, "2024-01-15T10:00:01Z ERROR boom"),
        (3, "java.lang.NullPointerException: x"),
        (4, "\tat com.example.Foo.bar(Foo.java:1)"),
        (5, "2024-01-15T10:00:02Z WARN done"),
    ]
    pr = parse_file_lines(Path("test.log"), _cfg(), lines)
    assert len(pr.records) == 3
    err = pr.records[1]
    assert err.level == "ERROR"
    assert "NullPointerException" in (err.stacktrace or "")
    assert "at com.example" in (err.stacktrace or "")
