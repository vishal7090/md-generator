from __future__ import annotations

from src.options import ConvertOptions


def convert_options_from_query(
    *,
    enable_office: bool = True,
    image_ocr: bool = False,
    pdf_ocr: bool = False,
    max_bytes: int = 512_000,
    expand_nested_zips: bool = True,
    max_nested_zip_depth: int = 16,
    repo_root: str | None = None,
) -> ConvertOptions:
    """Map API query parameters to ConvertOptions."""
    return ConvertOptions(
        artifact_layout=True,
        verbose=False,
        enable_office=enable_office,
        image_ocr=image_ocr,
        pdf_ocr=pdf_ocr,
        max_bytes=max_bytes,
        repo_root=repo_root,
        expand_nested_zips=expand_nested_zips,
        max_nested_zip_depth=max_nested_zip_depth,
    )
