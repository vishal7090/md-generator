from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from md_generator.url.crawl import run_crawl, run_crawl_async
from md_generator.url.fetch import fetch_html, new_client
from md_generator.url.options import ConvertOptions
from md_generator.url.page_convert import (
    convert_one_page_artifact,
    convert_one_page_classic,
    write_crawl_manifest,
)
from md_generator.url.extract import url_to_slug


def run_single(
    seed_url: str,
    output: Path,
    options: ConvertOptions,
    client: httpx.Client,
) -> None:
    fr = fetch_html(seed_url, client, options)
    if options.artifact_layout:
        output.mkdir(parents=True, exist_ok=True)
        meta = convert_one_page_artifact(fr.final_url, fr.text, output, options, client)
        write_crawl_manifest(
            output,
            [{"url": fr.final_url, "title": meta.get("title"), "path": "document.md"}],
        )
    else:
        if output.suffix.lower() != ".md":
            raise ValueError("Classic mode requires output path to end with .md")
        convert_one_page_classic(fr.final_url, fr.text, output, options, client)


def convert_urls_bulk(
    urls: list[str],
    output_parent: Path,
    options: ConvertOptions,
    client: httpx.Client,
) -> list[dict]:
    output_parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for i, u in enumerate(urls):
        slug = url_to_slug(u, i + 1)
        sub = output_parent / slug
        sub.mkdir(parents=True, exist_ok=True)
        leaf = options.with_overrides(artifact_layout=True, crawl=False)
        try:
            fr = fetch_html(u, client, leaf)
            convert_one_page_artifact(fr.final_url, fr.text, sub, leaf, client)
            entries.append(
                {
                    "slug": slug,
                    "url": fr.final_url,
                    "path": f"{slug}/document.md",
                }
            )
        except Exception as e:
            entries.append({"slug": slug, "url": u, "error": str(e)})
    lines = ["# Bulk URL conversion", ""]
    for e in entries:
        if e.get("error"):
            lines.append(f"- {e['url']}: **{e['error']}**")
        else:
            lines.append(f"- [{e['url']}]({e['path']})")
    lines.append("")
    (output_parent / "document.md").write_text("\n".join(lines), encoding="utf-8")
    write_crawl_manifest(output_parent, entries)
    return entries


def convert_url(seed_url: str, output: Path, options: ConvertOptions) -> None:
    with new_client(options) as client:
        if options.crawl:
            if not options.artifact_layout:
                raise ValueError("--artifact-layout is required when using --crawl")
            if options.async_crawl:
                asyncio.run(run_crawl_async(seed_url, output, options, client))
            else:
                run_crawl(seed_url, output, options, client)
        else:
            run_single(seed_url, output, options, client)


def convert_urls_from_list(
    urls: list[str],
    output_parent: Path,
    options: ConvertOptions,
) -> None:
    with new_client(options) as client:
        convert_urls_bulk(urls, output_parent, options, client)


def convert_url_job(
    seed_url: str | None,
    urls: list[str] | None,
    output: Path,
    options: ConvertOptions,
) -> None:
    """Used by API: exactly one of seed_url or urls (non-empty)."""
    with new_client(options) as client:
        if urls and len(urls) > 1:
            convert_urls_bulk(urls, output, options, client)
            return
        if urls and len(urls) == 1:
            u = urls[0]
            if options.crawl:
                if options.async_crawl:
                    asyncio.run(run_crawl_async(u, output, options, client))
                else:
                    run_crawl(u, output, options, client)
            else:
                run_single(u, output, options, client)
            return
        if seed_url:
            if options.crawl:
                if options.async_crawl:
                    asyncio.run(run_crawl_async(seed_url, output, options, client))
                else:
                    run_crawl(seed_url, output, options, client)
            else:
                run_single(seed_url, output, options, client)
            return
        raise ValueError("No URL provided")
