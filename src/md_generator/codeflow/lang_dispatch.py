"""Map file extensions to parser language keys and interpret ``ScanConfig.languages``."""

from __future__ import annotations

from pathlib import Path

# language key -> extensions scanned for that backend
LANG_EXTENSIONS: dict[str, frozenset[str]] = {
    "python": frozenset({".py"}),
    "java": frozenset({".java"}),
    "javascript": frozenset({".js", ".jsx", ".mjs", ".cjs"}),
    "typescript": frozenset({".ts", ".mts", ".cts"}),
    "tsx": frozenset({".tsx"}),
    "cpp": frozenset({".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}),
    "go": frozenset({".go"}),
    "php": frozenset({".php"}),
}

# All keys used when ``languages`` is ``mixed``
MIXED_LANG_KEYS: frozenset[str] = frozenset(LANG_EXTENSIONS.keys())


def normalize_language_filter(languages: str) -> frozenset[str]:
    """Return allowed parser language keys for a scan."""
    s = (languages or "mixed").strip().lower()
    if s == "mixed":
        return MIXED_LANG_KEYS
    parts: list[str] = []
    for p in s.split(","):
        p = p.strip().lower()
        if not p:
            continue
        if p in ("js", "javascript"):
            parts.append("javascript")
        elif p in ("ts", "typescript"):
            parts.append("typescript")
        elif p == "tsx":
            parts.append("tsx")
        elif p in ("c", "c++", "cxx", "cpp", "cplusplus"):
            parts.append("cpp")
        else:
            parts.append(p)
    return frozenset(parts) if parts else MIXED_LANG_KEYS


def extensions_for_languages(allowed: frozenset[str]) -> set[str]:
    exts: set[str] = set()
    for lang in allowed:
        exts |= set(LANG_EXTENSIONS.get(lang, frozenset()))
    return exts


def lang_for_path(path: Path) -> str:
    suf = path.suffix.lower()
    for lang, exts in LANG_EXTENSIONS.items():
        if suf in exts:
            return lang
    return "unknown"


def should_parse_file_lang(file_lang: str, allowed: frozenset[str]) -> bool:
    if file_lang == "unknown":
        return False
    return file_lang in allowed
