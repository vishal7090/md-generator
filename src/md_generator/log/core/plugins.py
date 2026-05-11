from __future__ import annotations

import importlib
from typing import Protocol, runtime_checkable

from md_generator.log.parser.models import LogRecord


@runtime_checkable
class LogEnricherPlugin(Protocol):
    def enrich(self, record: LogRecord) -> LogRecord: ...


def load_enrichers(specs: list[str]) -> list[LogEnricherPlugin]:
    out: list[LogEnricherPlugin] = []
    for spec in specs:
        if ":" not in spec:
            continue
        mod_name, _, attr = spec.partition(":")
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr, None)
        if obj is None:
            continue
        inst = obj() if callable(obj) else obj
        if isinstance(inst, LogEnricherPlugin):
            out.append(inst)
    return out


def run_enricher_plugins(record: LogRecord, plugins: list[LogEnricherPlugin]) -> LogRecord:
    r = record
    for p in plugins:
        r = p.enrich(r)
    return r
