from __future__ import annotations

from md_generator.log.config.preset_loader import list_preset_names
from md_generator.log.core.run_config import load_preset
from md_generator.log.parser.json_line_parser import try_parse_json_log_line
from md_generator.log.parser.regex_parser import try_structured_match
from md_generator.log.utils.regex import compile_optional

_BUILTIN_PRESET_ORDER = ("springboot", "logback", "generic", "json")


def _preset_candidates(preset_dirs: list[str] | None) -> list[str]:
    names = list_preset_names(preset_dirs)
    ordered: list[str] = []
    for n in _BUILTIN_PRESET_ORDER:
        if n in names:
            ordered.append(n)
    for n in names:
        if n not in ordered:
            ordered.append(n)
    return ordered


def _score_preset(name: str, lines: list[str], preset_dirs: list[str] | None) -> int:
    data = load_preset(name, preset_dirs)
    parser = data.get("parser") or {}
    preset_id = (parser.get("preset") or name).lower()
    if preset_id == "json":
        return sum(1 for line in lines if try_parse_json_log_line(line))
    rx = parser.get("line_regex")
    if not rx:
        return 0
    pat = compile_optional(str(rx))
    if not pat:
        return 0
    return sum(1 for line in lines if try_structured_match(line, pat))


def select_line_regex_for_sample(
    sample: str,
    *,
    max_lines: int = 200,
    preset_dirs: list[str] | None = None,
) -> str | None:
    """Pick best preset regex (None when json preset wins)."""
    name = select_preset_for_sample(sample, max_lines=max_lines, preset_dirs=preset_dirs)
    if not name or name.lower() == "json":
        return None
    data = load_preset(name, preset_dirs)
    rx = (data.get("parser") or {}).get("line_regex")
    return str(rx) if rx else None


def select_preset_for_sample(
    sample: str,
    *,
    max_lines: int = 200,
    preset_dirs: list[str] | None = None,
) -> str | None:
    """Return best matching preset name (including json and user presets)."""
    lines = [ln for ln in sample.splitlines()[:max_lines] if ln.strip()]
    if not lines:
        return None
    best_name: str | None = None
    best_score = 0
    for name in _preset_candidates(preset_dirs):
        score = _score_preset(name, lines, preset_dirs)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name
