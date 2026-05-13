from __future__ import annotations

from typing import Protocol, runtime_checkable

from md_generator.log.parser.models import LogRecord


@runtime_checkable
class ParserPlugin(Protocol):
    def can_parse(self, sample: str) -> bool: ...
    def parse(self, lines: list[str]) -> list[LogRecord]: ...
