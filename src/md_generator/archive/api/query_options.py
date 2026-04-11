from __future__ import annotations

from md_generator.archive.options import DEFAULT_IMAGE_TO_MD_ENGINES, ConvertOptions


def convert_options_from_query(
    *,
    enable_office: bool = True,
    image_ocr: bool = False,
    pdf_ocr: bool = False,
    max_bytes: int = 512_000,
    expand_nested_zips: bool = True,
    max_nested_zip_depth: int = 16,
    repo_root: str | None = None,
    use_image_to_md: bool = True,
    image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES,
    image_to_md_strategy: str = "best",
    image_to_md_title: str = "",
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
        use_image_to_md=use_image_to_md,
        image_to_md_engines=(image_to_md_engines or DEFAULT_IMAGE_TO_MD_ENGINES).strip()
        or DEFAULT_IMAGE_TO_MD_ENGINES,
        image_to_md_strategy=image_to_md_strategy if image_to_md_strategy in ("best", "compare") else "best",
        image_to_md_title=(image_to_md_title or "").strip(),
    )
