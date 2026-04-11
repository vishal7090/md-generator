from __future__ import annotations

from dataclasses import dataclass

# Default OCR stack for the image-to-md post-pass (order matters for "best" tie-break).
DEFAULT_IMAGE_TO_MD_ENGINES = "paddle,easy,tess"


@dataclass
class ConvertOptions:
    """Options for ZIP → Markdown conversion."""

    verbose: bool = False
    artifact_layout: bool = True
    enable_office: bool = True
    image_ocr: bool = False
    pdf_ocr: bool = False
    max_bytes: int = 512_000
    repo_root: str | None = None  # deprecated; ignored (converters run in-process)
    expand_nested_zips: bool = True
    max_nested_zip_depth: int = 16
    # Post-pass: run sibling image-to-md on all rasters under assets/files + assets/images.
    use_image_to_md: bool = True
    image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES
    image_to_md_strategy: str = "best"  # best | compare
    image_to_md_title: str = ""
