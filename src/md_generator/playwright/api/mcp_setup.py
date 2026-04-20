from __future__ import annotations

import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.playwright.api.convert_runner import build_artifact_zip_bytes
from md_generator.playwright.options import PlaywrightOptions, WaitUntil


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "playwright-to-md",
        instructions=(
            "Render JavaScript-heavy pages with Playwright, extract readable content, "
            "and return a temporary artifact.zip path on the server (Markdown + downloaded images)."
        ),
        streamable_http_path=path,
    )

    @mcp.tool()
    def convert_spa_url_to_artifact_zip(
        url: str,
        navigation_timeout_seconds: float = 60.0,
        wait_selector: str | None = None,
        wait_until: WaitUntil = "networkidle",
        max_scroll_rounds: int = 12,
        headless: bool = True,
        use_readability: bool = True,
        chunk_markdown: bool = True,
    ) -> str:
        """Fetch one URL with a headless browser, convert to Markdown + assets, return artifact.zip path."""
        u = url.strip()
        if not u.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        opts = PlaywrightOptions(
            navigation_timeout_ms=navigation_timeout_seconds * 1000.0,
            wait_selector=wait_selector,
            wait_until=wait_until,
            max_scroll_rounds=max_scroll_rounds,
            headless=headless,
            use_readability=use_readability,
            chunk_markdown=chunk_markdown,
            verbose=False,
        )
        data = build_artifact_zip_bytes(url=u, urls=None, options=opts)
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="playwright-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    sub = mcp.streamable_http_app()
    return mcp, sub
