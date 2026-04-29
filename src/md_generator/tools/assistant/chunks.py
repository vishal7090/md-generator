from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    heading: str
    source_path: str


_HEADING = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def chunk_markdown(text: str, source_path: str, max_chunk_chars: int = 4000) -> list[Chunk]:
    """Split markdown on `##` headings (keeps heading line in chunk)."""
    parts = _HEADING.split(text)
    if len(parts) == 1:
        body = parts[0].strip()
        if not body:
            return []
        return [_clip_chunk(Chunk(text=body, heading="(document)", source_path=source_path), max_chunk_chars)]
    out: list[Chunk] = []
    # parts[0] is preamble before first ##
    if parts[0].strip():
        out.append(
            _clip_chunk(
                Chunk(text=parts[0].strip(), heading="(preamble)", source_path=source_path),
                max_chunk_chars,
            )
        )
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        block = f"## {heading}\n\n{body}".strip()
        out.append(_clip_chunk(Chunk(text=block, heading=heading, source_path=source_path), max_chunk_chars))
    return out


def _clip_chunk(c: Chunk, max_chars: int) -> Chunk:
    if len(c.text) <= max_chars:
        return c
    return Chunk(text=c.text[: max_chars - 20] + "\n…(truncated)", heading=c.heading, source_path=c.source_path)


def strip_yaml_frontmatter(md: str) -> str:
    if not md.startswith("---"):
        return md
    parts = md.split("---", 2)
    if len(parts) < 3:
        return md
    return parts[2].lstrip("\n")
