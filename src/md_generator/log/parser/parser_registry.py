from __future__ import annotations

from md_generator.log.core.run_config import load_preset
from md_generator.log.parser.regex_parser import try_structured_match
from md_generator.log.utils.regex import compile_optional

_PRESET_ORDER = ("springboot", "generic")


def select_line_regex_for_sample(sample: str, *, max_lines: int = 200) -> str | None:
    """Pick best preset regex by counting structured matches on the first lines."""
    lines = sample.splitlines()[:max_lines]
    best_rx: str | None = None
    best_score = 0
    for name in _PRESET_ORDER:
        data = load_preset(name)
        rx = (data.get("parser") or {}).get("line_regex")
        if not rx:
            continue
        pat = compile_optional(str(rx))
        if not pat:
            continue
        score = sum(1 for line in lines if line.strip() and try_structured_match(line, pat))
        if score > best_score:
            best_score = score
            best_rx = str(rx)
    return best_rx
