from __future__ import annotations

import asyncio
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from md_generator.url.extract import extract_same_site_links, normalize_url, url_to_slug
from md_generator.url.fetch import fetch_html, fetch_html_async, new_async_client
from md_generator.url.options import ConvertOptions
from md_generator.url.page_convert import convert_one_page_artifact, write_crawl_manifest
from md_generator.url.robots_util import (
    allowed_by_robots,
    fetch_robots_parser,
    fetch_robots_parser_async,
)


def run_crawl(
    seed_url: str,
    output_parent: Path,
    options: ConvertOptions,
    client: httpx.Client,
) -> None:
    """Breadth-first crawl starting at seed_url; write pages under pages/<slug>/ and index document.md."""
    seed = normalize_url(seed_url)
    output_parent.mkdir(parents=True, exist_ok=True)
    robots_cache: dict[str, RobotFileParser | None] = {}
    pending: set[str] = set()
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(seed, 0)])
    pending.add(seed)
    manifest_pages: list[dict] = []
    pages_root = output_parent / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)
    page_idx = 0

    def robots_for(u: str) -> RobotFileParser | None:
        host = urlparse(u).netloc
        if host not in robots_cache:
            robots_cache[host] = fetch_robots_parser(client, u)
        return robots_cache[host]

    while queue and len(visited) < options.max_pages:
        url, depth = queue.popleft()
        nu = normalize_url(url)
        pending.discard(nu)
        if nu in visited:
            continue
        if options.obey_robots:
            rp = robots_for(nu)
            if not allowed_by_robots(rp, options.user_agent, nu, obey=True):
                manifest_pages.append({"url": nu, "skipped": "robots.txt disallow"})
                visited.add(nu)
                continue
        try:
            fr = fetch_html(nu, client, options)
        except Exception as e:
            manifest_pages.append({"url": nu, "error": str(e)})
            visited.add(nu)
            continue

        visited.add(nu)
        page_idx += 1
        slug = url_to_slug(fr.final_url, page_idx)
        page_dir = pages_root / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        leaf_opts = options.with_overrides(artifact_layout=True, crawl=False)
        meta = convert_one_page_artifact(fr.final_url, fr.text, page_dir, leaf_opts, client)
        manifest_pages.append(
            {
                "slug": slug,
                "path": f"pages/{slug}/document.md",
                **meta,
            }
        )

        if depth < options.max_depth and len(visited) < options.max_pages:
            for lk in extract_same_site_links(
                fr.text,
                fr.final_url,
                include_subdomains=options.include_subdomains,
            ):
                lk_n = normalize_url(lk)
                if lk_n in visited or lk_n in pending:
                    continue
                pending.add(lk_n)
                queue.append((lk_n, depth + 1))

        if options.crawl_delay_seconds > 0:
            time.sleep(options.crawl_delay_seconds)

    _write_crawl_index(output_parent, manifest_pages)


def _write_crawl_index(output_parent: Path, manifest_pages: list[dict]) -> None:
    index_lines = ["# Crawl results", ""]
    for p in manifest_pages:
        if p.get("error") or p.get("skipped"):
            index_lines.append(f"- {p['url']}: **{p.get('error') or p.get('skipped')}**")
        elif "path" in p:
            title = p.get("title") or p.get("url")
            index_lines.append(f"- [{title}]({p['path']})")
    index_lines.append("")
    (output_parent / "document.md").write_text("\n".join(index_lines), encoding="utf-8")
    write_crawl_manifest(output_parent, manifest_pages)


def _crawl_concurrency_cap(options: ConvertOptions) -> int:
    n = options.crawl_max_concurrency if options.async_crawl else 1
    return max(1, min(32, n))


async def run_crawl_async(
    seed_url: str,
    output_parent: Path,
    options: ConvertOptions,
    sync_client: httpx.Client,
) -> None:
    """Async crawl: httpx.AsyncClient for HTML/robots; sync client for asset downloads in convert."""
    seed = normalize_url(seed_url)
    output_parent.mkdir(parents=True, exist_ok=True)
    robots_cache: dict[str, RobotFileParser | None] = {}
    robots_lock = asyncio.Lock()
    pending: set[str] = set()
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(seed, 0)])
    pending.add(seed)
    manifest_pages: list[dict] = []
    pages_root = output_parent / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)
    page_idx = 0
    cap = _crawl_concurrency_cap(options)
    sem = asyncio.Semaphore(cap)

    async def robots_for_async(aclient: httpx.AsyncClient, u: str) -> RobotFileParser | None:
        host = urlparse(u).netloc
        async with robots_lock:
            if host in robots_cache:
                return robots_cache[host]
        pol = await fetch_robots_parser_async(aclient, u)
        async with robots_lock:
            if host not in robots_cache:
                robots_cache[host] = pol
            return robots_cache[host]

    async with new_async_client(options) as aclient:

        async def fetch_one(nu: str) -> object:
            async with sem:
                return await fetch_html_async(nu, aclient, options)

        while queue and len(visited) < options.max_pages:
            batch: list[tuple[str, int]] = []
            while queue and len(batch) < cap and len(visited) + len(batch) < options.max_pages:
                url, depth = queue.popleft()
                nu = normalize_url(url)
                pending.discard(nu)
                if nu in visited:
                    continue
                if options.obey_robots:
                    rp = await robots_for_async(aclient, nu)
                    if not allowed_by_robots(rp, options.user_agent, nu, obey=True):
                        manifest_pages.append({"url": nu, "skipped": "robots.txt disallow"})
                        visited.add(nu)
                        continue
                batch.append((nu, depth))

            if not batch:
                continue

            tasks = [asyncio.create_task(fetch_one(nu)) for nu, _ in batch]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            for (nu, depth), res in zip(batch, raw_results):
                if isinstance(res, Exception):
                    manifest_pages.append({"url": nu, "error": str(res)})
                    visited.add(nu)
                    continue

                fr = res
                visited.add(nu)
                page_idx += 1
                slug = url_to_slug(fr.final_url, page_idx)
                page_dir = pages_root / slug
                page_dir.mkdir(parents=True, exist_ok=True)
                leaf_opts = options.with_overrides(artifact_layout=True, crawl=False)
                meta = await asyncio.to_thread(
                    convert_one_page_artifact,
                    fr.final_url,
                    fr.text,
                    page_dir,
                    leaf_opts,
                    sync_client,
                )
                manifest_pages.append(
                    {
                        "slug": slug,
                        "path": f"pages/{slug}/document.md",
                        **meta,
                    }
                )

                if depth < options.max_depth and len(visited) < options.max_pages:
                    for lk in extract_same_site_links(
                        fr.text,
                        fr.final_url,
                        include_subdomains=options.include_subdomains,
                    ):
                        lk_n = normalize_url(lk)
                        if lk_n in visited or lk_n in pending:
                            continue
                        pending.add(lk_n)
                        queue.append((lk_n, depth + 1))

                if options.crawl_delay_seconds > 0:
                    await asyncio.sleep(options.crawl_delay_seconds)

    _write_crawl_index(output_parent, manifest_pages)
