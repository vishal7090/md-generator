from __future__ import annotations

from md_generator.url.options import DEFAULT_IMAGE_TO_MD_ENGINES, ConvertOptions


def convert_options_from_query(
    *,
    crawl: bool = False,
    async_crawl: bool = False,
    crawl_max_concurrency: int = 4,
    max_depth: int = 2,
    max_pages: int = 30,
    crawl_delay_seconds: float = 0.5,
    obey_robots: bool = True,
    include_subdomains: bool = True,
    table_csv: bool = True,
    download_linked_files: bool = True,
    timeout_seconds: float = 30.0,
    max_response_bytes: int = 10 * 1024 * 1024,
    convert_downloaded_assets: bool = True,
    convert_downloaded_images: bool = True,
    convert_downloaded_image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES,
    convert_downloaded_image_to_md_strategy: str = "best",
    convert_downloaded_image_to_md_title: str = "",
    post_convert_pdf_ocr: bool = False,
    post_convert_pdf_ocr_min_chars: int = 40,
    post_convert_ppt_embedded_deep: bool = True,
    max_linked_files: int = 40,
    max_downloaded_images: int = 50,
) -> ConvertOptions:
    """Map API query parameters to ConvertOptions (artifact layout forced at call site)."""
    return ConvertOptions(
        artifact_layout=True,
        crawl=crawl,
        async_crawl=async_crawl,
        crawl_max_concurrency=crawl_max_concurrency,
        max_depth=max_depth,
        max_pages=max_pages,
        crawl_delay_seconds=crawl_delay_seconds,
        obey_robots=obey_robots,
        include_subdomains=include_subdomains,
        table_csv=table_csv,
        download_linked_files=download_linked_files,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        convert_downloaded_assets=convert_downloaded_assets,
        convert_downloaded_images=convert_downloaded_images,
        convert_downloaded_image_to_md_engines=(
            (convert_downloaded_image_to_md_engines or "").strip() or DEFAULT_IMAGE_TO_MD_ENGINES
        ),
        convert_downloaded_image_to_md_strategy=convert_downloaded_image_to_md_strategy
        if convert_downloaded_image_to_md_strategy in ("best", "compare")
        else "best",
        convert_downloaded_image_to_md_title=convert_downloaded_image_to_md_title,
        post_convert_pdf_ocr=post_convert_pdf_ocr,
        post_convert_pdf_ocr_min_chars=post_convert_pdf_ocr_min_chars,
        post_convert_ppt_embedded_deep=post_convert_ppt_embedded_deep,
        max_linked_files=max_linked_files,
        max_downloaded_images=max_downloaded_images,
        verbose=False,
    )
