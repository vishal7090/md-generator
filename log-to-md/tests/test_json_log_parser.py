from __future__ import annotations

from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.parser.multiline_parser import parse_file_lines


def test_json_preset_parses_jsonl() -> None:
    from dataclasses import replace

    cfg = replace(LogRunConfig().normalized(), parser=replace(LogRunConfig().parser, preset="json"))
    lines = [
        (1, '{"level":"ERROR","message":"boom","user":"@u","ip":"10.0.0.1"}'),
        (2, '{"timestamp":"2024-01-01T00:00:00Z","severity":"INFO","msg":"ok"}'),
    ]
    pr = parse_file_lines(Path("x.jsonl"), cfg, lines)
    assert len(pr.records) == 2
    assert pr.records[0].level == "ERROR"
    assert "@u" in pr.records[0].message


def test_logback_preset_parses_thread_logger() -> None:
    from dataclasses import replace

    cfg = load_logback_cfg()
    line = "2024-06-01 18:00:00.123 [main] INFO  com.acme.App - hello user=@lb ip=1.2.3.4"
    pr = parse_file_lines(Path("app.log"), cfg, [(1, line)])
    assert len(pr.records) == 1
    assert pr.records[0].logger
    assert pr.records[0].thread == "main"


def load_logback_cfg() -> LogRunConfig:
    from dataclasses import replace

    from md_generator.log.core.run_config import load_preset

    data = load_preset("logback")
    rx = (data.get("parser") or {}).get("line_regex")
    base = LogRunConfig().normalized()
    return replace(base, parser=replace(base.parser, preset="logback", line_regex=rx))
