"""Paths, image filenames, artifact bundle layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ResolvedOutput:
    """Where to write Markdown and extracted images."""

    markdown_path: Path
    images_dir: Path
    artifact_layout: bool


def resolve_output(
    output: Path,
    artifact_layout: bool,
    images_dir: Optional[Path],
) -> ResolvedOutput:
    """
    Classic: output is the .md file path; images default to <parent>/images.
    Artifact: output is a directory; writes document.md and assets/images/.
    """
    output = Path(output).resolve()
    if artifact_layout:
        out_dir = output
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / "document.md"
        img_dir = out_dir / "assets" / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        return ResolvedOutput(md_path, img_dir, True)
    md_path = output
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if images_dir is not None:
        img_dir = Path(images_dir).resolve()
    else:
        img_dir = (md_path.parent / "images").resolve()
    img_dir.mkdir(parents=True, exist_ok=True)
    return ResolvedOutput(md_path, img_dir, False)


def image_filename(page_1based: int, index: int, ext: str) -> str:
    ext = ext.lstrip(".").lower() if ext else "bin"
    return f"page_{page_1based}_img_{index}.{ext}"


def markdown_link_to_image(markdown_path: Path, image_path: Path) -> str:
    """Relative POSIX path from markdown file to image for ![](...) links."""
    md_parent = markdown_path.parent
    rel = Path(image_path).resolve().relative_to(md_parent)
    return rel.as_posix()
