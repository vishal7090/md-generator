from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.lang_dispatch import (
    extensions_for_languages,
    lang_for_path,
    normalize_language_filter,
    should_parse_file_lang,
)


def test_normalize_mixed_includes_js() -> None:
    exts = extensions_for_languages(normalize_language_filter("mixed"))
    assert ".ts" in exts
    assert ".go" in exts


def test_lang_for_path() -> None:
    assert lang_for_path(Path("a.tsx")) == "tsx"
    assert lang_for_path(Path("b.go")) == "go"


def test_should_parse_filter() -> None:
    allowed = normalize_language_filter("python,javascript")
    assert should_parse_file_lang("python", allowed)
    assert should_parse_file_lang("javascript", allowed)
    assert not should_parse_file_lang("go", allowed)
