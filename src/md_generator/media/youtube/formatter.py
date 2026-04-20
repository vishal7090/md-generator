"""Render YouTube conversion result as Markdown."""

from __future__ import annotations

from typing import Any


def _format_seconds(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    return f"{seconds:.2f}s"


class YouTubeMarkdownFormatter:
    """Build Markdown: # YouTube, title, metadata, description, timestamped transcript."""

    def format(self, result: Any) -> str:
        meta: dict[str, Any] = dict(result.metadata or {})
        title = (meta.get("title") or "Untitled").strip() or "Untitled"
        parts = [
            "# YouTube",
            "",
            f"## {title}",
            "",
            "### Video Metadata",
            "",
        ]
        views = meta.get("views")
        if views is not None:
            parts.append(f"* **Views:** {views}")
        dur = meta.get("duration_seconds")
        if dur is not None:
            parts.append(f"* **Duration:** {dur}")
        kw = meta.get("keywords")
        if kw:
            parts.append(f"* **Keywords:** {kw}")
        parts.append(f"* **URL:** {meta.get('url', '')}")
        if meta.get("author"):
            parts.append(f"* **Channel:** {meta['author']}")
        if meta.get("transcript_source"):
            parts.append(f"* **Transcript source:** {meta['transcript_source']}")

        parts.extend(["", "### Description", ""])
        desc = (meta.get("description") or "").strip()
        parts.append(desc if desc else "_(no description)_")

        parts.extend(["", "### Transcript", ""])
        segments: list[dict[str, Any]] = list(result.segments or [])
        if not segments:
            parts.append("_(no transcript)_")
        else:
            for seg in segments:
                start = float(seg.get("start", 0.0))
                text = str(seg.get("text", "")).strip()
                if text:
                    parts.append(f"* [{_format_seconds(start)}] {text}")

        return "\n".join(parts).rstrip() + "\n"
