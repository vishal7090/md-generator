from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConvertOptions:
    """Options for ZIP → Markdown conversion."""

    verbose: bool = False
    artifact_layout: bool = True
    enable_office: bool = True
    image_ocr: bool = False
    pdf_ocr: bool = False
    max_bytes: int = 512_000
    repo_root: str | None = None  # override MD_GENERATOR_ROOT / auto-detect
    expand_nested_zips: bool = True
    max_nested_zip_depth: int = 16
