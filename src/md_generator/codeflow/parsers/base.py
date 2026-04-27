from __future__ import annotations

from pathlib import Path
from typing import Protocol

from md_generator.codeflow.models.ir import FileParseResult


class LanguageParser(Protocol):
    language: str

    def parse_file(self, path: Path, project_root: Path) -> FileParseResult:
        ...


class ParserRegistry:
    def __init__(self) -> None:
        self._by_lang: dict[str, LanguageParser] = {}

    def register(self, parser: LanguageParser) -> None:
        self._by_lang[parser.language] = parser

    def get(self, lang: str) -> LanguageParser | None:
        return self._by_lang.get(lang)

    def parse_file(self, path: Path, project_root: Path, lang: str) -> FileParseResult | None:
        p = self.get(lang)
        if not p:
            return None
        return p.parse_file(path, project_root)


def register_defaults(reg: ParserRegistry) -> None:
    from md_generator.codeflow.parsers.java_parser import JavaParser
    from md_generator.codeflow.parsers.python_parser import PythonParser

    reg.register(PythonParser())
    reg.register(JavaParser())
