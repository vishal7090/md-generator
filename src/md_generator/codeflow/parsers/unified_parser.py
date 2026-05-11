"""Single entry for per-file parsing with optional backend mode (C++ clang vs Tree-sitter)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.parsers.base import ParserRegistry
from md_generator.codeflow.parsers.cpp_parser import CppParser

ParserMode = Literal["auto", "treesitter", "external"]


def parse_source_file(
    reg: ParserRegistry,
    path: Path,
    project_root: Path,
    lang: str,
    mode: ParserMode,
) -> FileParseResult | None:
    """Dispatch to registry or C++-specific paths when ``mode`` requests it."""
    if mode == "auto":
        return reg.parse_file(path, project_root, lang)
    if lang == "cpp":
        cpp = CppParser()
        if mode == "treesitter":
            return cpp.parse_treesitter_only(path, project_root)
        if mode == "external":
            return cpp.parse_clang_only(path, project_root)
    return reg.parse_file(path, project_root, lang)
