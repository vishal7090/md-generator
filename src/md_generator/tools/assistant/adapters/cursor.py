from __future__ import annotations

from ..agent import AskResult


def to_cursor_rules_markdown(result: AskResult, *, title: str = "mdengine — grounded context") -> str:
    """Markdown suitable for `.cursor/rules/` or pasting as a workspace rule."""
    lines = [
        "---",
        f"description: {title} (resolved skills: {', '.join(result.resolved_skill_ids)})",
        "alwaysApply: false",
        "---",
        "",
        f"User query: {result.query}",
        "",
        "## Grounded context",
        "",
        result.context_markdown,
    ]
    return "\n".join(lines).rstrip() + "\n"
