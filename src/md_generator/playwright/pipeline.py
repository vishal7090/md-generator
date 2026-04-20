from __future__ import annotations

import asyncio
from pathlib import Path

from md_generator.playwright import assets, chunker, extractor, html_to_md, playwright_fetcher
from md_generator.playwright.options import PlaywrightOptions


def _metadata_header(url: str) -> str:
    return "\n".join(
        [
            "---",
            f"source: {url}",
            "type: url",
            "---",
            "",
        ]
    )


async def convert_url_to_md(
    url: str,
    output_dir: Path | str,
    options: PlaywrightOptions | None = None,
) -> Path:
    """
    Fetch rendered HTML, extract main content, convert to Markdown, download images, chunk, save.
    """
    opts = options or PlaywrightOptions()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw_html = await playwright_fetcher.fetch_rendered_html(url, options=opts)
    main_html = extractor.extract_main_content(raw_html)
    md = html_to_md.convert_html_to_markdown(
        main_html,
        use_readability=opts.use_readability,
        page_url=url,
    )

    md_assets = await asyncio.to_thread(
        assets.process_assets,
        md,
        url,
        out,
        max_images=opts.max_images,
        max_image_bytes=opts.max_image_bytes,
        asset_timeout_seconds=opts.asset_timeout_seconds,
    )

    final_body = (
        chunker.chunk_markdown(
            md_assets,
            max_tokens=opts.max_chunk_tokens,
            chars_per_token=opts.chars_per_token,
        )
        if opts.chunk_markdown
        else md_assets
    )

    document = _metadata_header(url) + final_body.strip() + "\n"
    doc_path = out / "document.md"
    doc_path.write_text(document, encoding="utf-8")
    return doc_path
