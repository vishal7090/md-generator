from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from md_generator.url.crawl import run_crawl, run_crawl_async
from md_generator.url.fetch import FetchResult
from md_generator.url.options import ConvertOptions


def test_run_crawl_two_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Breadth-first crawl with fetch_html patched to a tiny two-page site."""

    def fake_fetch(url: str, client, options):
        u = url.rstrip("/")
        if u.endswith("two") or "two" in url.split("/")[-1]:
            html = "<!DOCTYPE html><html><body><p>Page two</p></body></html>"
            final = "https://crawl.test/two"
        else:
            html = """<!DOCTYPE html><html><body>
            <h1>One</h1>
            <a href="https://crawl.test/two">next</a>
            </body></html>"""
            final = "https://crawl.test/"
        return FetchResult(
            url=url,
            final_url=final,
            status_code=200,
            content_type="text/html",
            text=html,
        )

    monkeypatch.setattr("md_generator.url.crawl.fetch_html", fake_fetch)

    transport = httpx.MockTransport(lambda r: httpx.Response(404))
    client = httpx.Client(transport=transport)
    opts = ConvertOptions(
        artifact_layout=True,
        crawl=True,
        max_depth=2,
        max_pages=5,
        crawl_delay_seconds=0,
        obey_robots=False,
        include_subdomains=True,
    )
    out = tmp_path / "crawl_out"
    run_crawl("https://crawl.test/", out, opts, client)
    client.close()

    index = (out / "document.md").read_text(encoding="utf-8")
    assert "Crawl results" in index
    pages = list((out / "pages").glob("*/document.md"))
    assert len(pages) >= 2


def test_run_crawl_async_two_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_fetch_async(url: str, client, options):
        u = url.rstrip("/")
        if u.endswith("two") or "two" in url.split("/")[-1]:
            html = "<!DOCTYPE html><html><body><p>Page two</p></body></html>"
            final = "https://crawl.test/two"
        else:
            html = """<!DOCTYPE html><html><body>
            <h1>One</h1>
            <a href="https://crawl.test/two">next</a>
            </body></html>"""
            final = "https://crawl.test/"
        return FetchResult(
            url=url,
            final_url=final,
            status_code=200,
            content_type="text/html",
            text=html,
        )

    monkeypatch.setattr("md_generator.url.crawl.fetch_html_async", fake_fetch_async)

    transport = httpx.MockTransport(lambda r: httpx.Response(404))
    client = httpx.Client(transport=transport)
    opts = ConvertOptions(
        artifact_layout=True,
        crawl=True,
        async_crawl=True,
        crawl_max_concurrency=2,
        max_depth=2,
        max_pages=5,
        crawl_delay_seconds=0,
        obey_robots=False,
        include_subdomains=True,
    )
    out = tmp_path / "crawl_async_out"
    asyncio.run(run_crawl_async("https://crawl.test/", out, opts, client))
    client.close()

    index = (out / "document.md").read_text(encoding="utf-8")
    assert "Crawl results" in index
    pages = list((out / "pages").glob("*/document.md"))
    assert len(pages) >= 2
