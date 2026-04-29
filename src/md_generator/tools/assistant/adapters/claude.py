from __future__ import annotations

import json
from typing import Any

from ..agent import AskResult


def to_claude_project_prompt(result: AskResult) -> str:
    """Single project/system prompt string suitable for Claude project instructions."""
    header = (
        "# mdengine — grounded system prompt\n\n"
        "Use only the following context for mdengine / md_generator facts. "
        "For behavior not listed, defer to upstream README and installed CLI `--help`.\n\n"
        f"**Resolved skill ids:** {', '.join(result.resolved_skill_ids)}\n\n"
        f"**Routing scores (areas):** {json.dumps(result.scores, sort_keys=True)}\n\n"
        "---\n\n"
    )
    return header + result.context_markdown


def to_claude_metadata_blob(result: AskResult) -> dict[str, Any]:
    """Sidecar JSON-friendly metadata (optional attachment in toolchains)."""
    return {
        "resolved_skill_ids": result.resolved_skill_ids,
        "resolved_areas": result.resolved_areas,
        "scores": result.scores,
        "rag_used": result.rag_used,
        "user_query": result.query,
    }
