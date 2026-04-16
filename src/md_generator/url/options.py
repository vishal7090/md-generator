from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

# Default OCR stack for the image-to-md post-pass (order matters for "best" tie-break).
DEFAULT_IMAGE_TO_MD_ENGINES = "paddle,easy,tess"


@dataclass
class ConvertOptions:
    """CLI and API flags for URL → Markdown conversion."""

    artifact_layout: bool = False
    images_dir: Path | None = None
    verbose: bool = False

    timeout_seconds: float = 30.0
    max_response_bytes: int = 10 * 1024 * 1024
    user_agent: str = "mdengine-url-to-md/0.1 (+https://github.com/vishal7090/md-generator)"

    table_csv: bool = True
    download_linked_files: bool = True
    linked_file_extensions: tuple[str, ...] = (
        ".pdf",
        ".zip",
        ".docx",
        ".xlsx",
        ".xlsm",
        ".csv",
        ".pptx",
        ".txt",
        ".json",
        ".xml",
    )
    max_linked_files: int = 40
    max_downloaded_images: int = 50

    crawl: bool = False
    max_depth: int = 2
    max_pages: int = 30
    crawl_delay_seconds: float = 0.5
    async_crawl: bool = False
    crawl_max_concurrency: int = 4
    obey_robots: bool = True
    same_site_only: bool = True
    include_subdomains: bool = True

    convert_downloaded_assets: bool = True
    convert_downloaded_images: bool = True
    convert_downloaded_image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES
    convert_downloaded_image_to_md_strategy: str = "best"  # best | compare
    convert_downloaded_image_to_md_title: str = ""
    post_convert_pdf_ocr: bool = False
    post_convert_pdf_ocr_min_chars: int = 40
    post_convert_ppt_embedded_deep: bool = True

    @classmethod
    def field_names(cls) -> set[str]:
        return {f.name for f in fields(cls)}

    def with_overrides(self, **kwargs: Any) -> ConvertOptions:
        known = self.field_names()
        clean = {k: v for k, v in kwargs.items() if k in known and v is not None}
        return replace(self, **clean)
