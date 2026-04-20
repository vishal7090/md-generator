from __future__ import annotations

import asyncio
from pathlib import Path

from md_generator.playwright.options import PlaywrightOptions


async def fetch_rendered_html(
    url: str,
    *,
    wait_selector: str | None = None,
    options: PlaywrightOptions | None = None,
) -> str:
    """
    Launch headless Chromium, load URL, wait for network settle / selector, scroll for lazy content.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise ImportError(
            "playwright is required. Install with: pip install playwright && playwright install chromium"
        ) from e

    opts = options or PlaywrightOptions()
    selector = wait_selector if wait_selector is not None else opts.wait_selector
    last_err: Exception | None = None

    for attempt in range(max(1, opts.max_retries)):
        try:
            return await _fetch_once(
                url,
                wait_selector=selector,
                options=opts,
            )
        except Exception as e:
            last_err = e
            if attempt + 1 >= opts.max_retries:
                break
            await asyncio.sleep(opts.retry_backoff_seconds * (attempt + 1))

    assert last_err is not None
    raise last_err


async def _fetch_once(
    url: str,
    *,
    wait_selector: str | None,
    options: PlaywrightOptions,
) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=options.headless)
        try:
            context = await browser.new_context(user_agent=options.user_agent)
            page = await context.new_page()
            try:
                await page.goto(
                    url,
                    wait_until=options.wait_until,
                    timeout=options.navigation_timeout_ms,
                )
            except Exception:
                if options.wait_until != "networkidle":
                    raise
                await page.goto(
                    url,
                    wait_until="load",
                    timeout=options.navigation_timeout_ms,
                )

            if wait_selector:
                await page.wait_for_selector(
                    wait_selector,
                    timeout=min(options.navigation_timeout_ms, 30_000.0),
                )

            await _scroll_for_lazy_content(page, options)

            html = await page.content()
            if options.save_raw_html_path:
                options.save_raw_html_path.parent.mkdir(parents=True, exist_ok=True)
                options.save_raw_html_path.write_text(html, encoding="utf-8")
            if options.screenshot_path:
                options.screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(options.screenshot_path), full_page=True)

            return html
        finally:
            await browser.close()


async def _scroll_for_lazy_content(page, options: PlaywrightOptions) -> None:
    prev = 0
    for _ in range(max(1, options.max_scroll_rounds)):
        height = await page.evaluate(
            """() => {
                window.scrollTo(0, document.body.scrollHeight);
                return document.body.scrollHeight;
            }"""
        )
        await asyncio.sleep(options.scroll_pause_ms / 1000.0)
        if isinstance(height, (int, float)) and height == prev:
            break
        prev = int(height) if height else 0
