"""Resolve output Markdown path (classic file or artifact layout)."""

from __future__ import annotations

from pathlib import Path


def resolve_markdown_output(output: Path, *, artifact_layout: bool) -> Path:
    """
    Classic: output is the path to the .md file.
    Artifact: output is a directory; writes document.md inside it.
    """
    output = Path(output).resolve()
    if artifact_layout:
        output.mkdir(parents=True, exist_ok=True)
        return output / "document.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    return output
