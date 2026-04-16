from __future__ import annotations

import json
from pathlib import Path

import httpx

from md_generator.url.assets import collect_and_download_assets, rewrite_markdown_urls
from md_generator.url.html_to_md import (
    append_table_csv_sidecars,
    html_fragment_to_markdown,
    readability_main_html,
)
from md_generator.url.options import ConvertOptions
from md_generator.url.post_convert_assets import process_downloaded_files


def write_crawl_manifest(out_root: Path, pages: list[dict]) -> None:
    manifest_dir = out_root / "assets"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "crawl_manifest.json").write_text(
        json.dumps({"pages": pages}, indent=2),
        encoding="utf-8",
    )


def convert_one_page_artifact(
    page_url: str,
    html: str,
    artifact_root: Path,
    options: ConvertOptions,
    client: httpx.Client,
) -> dict[str, str | None]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    summary, title = readability_main_html(html, page_url)
    body = html_fragment_to_markdown(summary)

    images_rel = Path("assets") / "images"
    files_rel = Path("assets") / "files"
    tables_dir = artifact_root / "assets" / "tables"

    url_map = collect_and_download_assets(
        html,
        page_url,
        output_dir=artifact_root,
        images_rel=images_rel,
        files_rel=files_rel,
        client=client,
        options=options,
    )
    body = rewrite_markdown_urls(body, url_map)

    if options.table_csv:
        # Use full document HTML so tables readability dropped are still captured as CSV.
        body += append_table_csv_sidecars(
            html,
            tables_dir,
            filename_prefix="page",
            link_prefix="assets/tables",
        )

    header = f"# {title or 'Page'}\n\n_Source: [{page_url}]({page_url})_\n\n"
    doc_text = header + body + "\n"
    doc_text += process_downloaded_files(artifact_root, options)
    (artifact_root / "document.md").write_text(doc_text, encoding="utf-8")
    return {"url": page_url, "title": title, "final_url": page_url}


def convert_one_page_classic(
    page_url: str,
    html: str,
    md_path: Path,
    options: ConvertOptions,
    client: httpx.Client,
) -> dict[str, str | None]:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    summary, title = readability_main_html(html, page_url)
    body = html_fragment_to_markdown(summary)
    out_dir = md_path.parent
    url_map = collect_and_download_assets(
        html,
        page_url,
        output_dir=out_dir,
        images_rel=Path("images"),
        files_rel=Path("files"),
        client=client,
        options=options,
    )
    body = rewrite_markdown_urls(body, url_map)
    if options.table_csv:
        tdir = out_dir / "tables"
        body += append_table_csv_sidecars(
            summary,
            tdir,
            filename_prefix="page",
            link_prefix="tables",
        )
    header = f"# {title or 'Page'}\n\n_Source: [{page_url}]({page_url})_\n\n"
    doc_text = header + body + "\n"
    doc_text += process_downloaded_files(md_path.parent, options)
    md_path.write_text(doc_text, encoding="utf-8")
    return {"url": page_url, "title": title}
