from __future__ import annotations

import json
from typing import Any

from ..agent import AskResult


def to_openai_messages(result: AskResult, *, system_extra: str | None = None) -> list[dict[str, Any]]:
    """Chat Completions-style message list (plain JSON-serializable dicts)."""
    system = (
        "You are an assistant helping with the mdengine (md_generator) Python distribution. "
        "Answer only using the following grounded context from generated skills. "
        "If something is not covered, say so and suggest `pip show mdengine` / CLI `--help`.\n\n"
        f"Resolved skills: {', '.join(result.resolved_skill_ids)}\n\n"
        f"{result.context_markdown}"
    )
    if system_extra:
        system = system + "\n\n" + system_extra.strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": result.query},
    ]


def openai_messages_json(result: AskResult, *, indent: int | None = 2) -> str:
    return json.dumps(to_openai_messages(result), indent=indent, ensure_ascii=False)
