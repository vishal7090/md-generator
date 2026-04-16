from __future__ import annotations

import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.url.api.convert_runner import build_artifact_zip_bytes
from md_generator.url.options import ConvertOptions


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "url-to-md",
        instructions="Convert public HTTP(S) HTML pages to Markdown artifact ZIP bundles.",
        streamable_http_path=path,
    )

    @mcp.tool()
    def convert_url_to_artifact_zip(
        url: str,
        crawl: bool = False,
        async_crawl: bool = False,
        crawl_max_concurrency: int = 4,
        max_depth: int = 2,
        max_pages: int = 30,
        obey_robots: bool = True,
    ) -> str:
        """Fetch URL(s), convert to Markdown + assets, return a temporary artifact.zip path on the server."""
        u = url.strip()
        if not u.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        opts = ConvertOptions(
            artifact_layout=True,
            crawl=crawl,
            async_crawl=async_crawl,
            crawl_max_concurrency=crawl_max_concurrency,
            max_depth=max_depth,
            max_pages=max_pages,
            obey_robots=obey_robots,
            verbose=False,
        )
        data = build_artifact_zip_bytes(url=u, urls=None, options=opts)
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="url-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    sub = mcp.streamable_http_app()
    return mcp, sub
