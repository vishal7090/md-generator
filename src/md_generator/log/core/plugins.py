from __future__ import annotations

import importlib
import time
from typing import Protocol, runtime_checkable

from md_generator.log.parser.models import LogRecord, ParseResult
from md_generator.sdk.parser_plugin import ParserPlugin


@runtime_checkable
class LogEnricherPlugin(Protocol):
    def enrich(self, record: LogRecord) -> LogRecord: ...


def _load_plugin_instances(specs: list[str], protocol: type) -> list:
    out: list = []
    for spec in specs:
        if ":" not in spec:
            continue
        mod_name, _, attr = spec.partition(":")
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr, None)
        if obj is None:
            continue
        inst = obj() if callable(obj) else obj
        if isinstance(inst, protocol):
            out.append(inst)
    return out


def load_enrichers(specs: list[str]) -> list[LogEnricherPlugin]:
    return _load_plugin_instances(specs, LogEnricherPlugin)


def load_parser_plugins(specs: list[str]) -> list[ParserPlugin]:
    return _load_plugin_instances(specs, ParserPlugin)


def run_enricher_plugins(record: LogRecord, plugins: list[LogEnricherPlugin]) -> LogRecord:
    r = record
    for p in plugins:
        r = p.enrich(r)
    return r


def try_parse_with_plugins(
    source_file,
    cfg,
    lines: list[tuple[int, str]],
) -> ParseResult | None:
    from pathlib import Path

    specs = cfg.plugins.parsers if hasattr(cfg, "plugins") else []
    plugins = load_parser_plugins(specs)
    if not plugins:
        return None
    path = Path(source_file)
    sample = "\n".join(text for _, text in lines[:100])
    text_lines = [text for _, text in lines]
    t0 = time.perf_counter()
    for plugin in plugins:
        if not plugin.can_parse(sample):
            continue
        from dataclasses import replace

        raw_records = plugin.parse(text_lines)
        records: list[LogRecord] = []
        for i, rec in enumerate(raw_records):
            ln = rec.line_number if rec.line_number > 0 else (lines[i][0] if i < len(lines) else i + 1)
            records.append(replace(rec, source_file=path, line_number=ln))
        ms = int((time.perf_counter() - t0) * 1000)
        return ParseResult(
            records=records,
            total_lines=len(lines),
            malformed_lines=max(0, len(lines) - len(records)),
            skipped_lines=0,
            parse_duration_ms=ms,
        )
    return None
