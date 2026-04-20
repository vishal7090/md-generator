from __future__ import annotations

import asyncio
import io
import zipfile
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from md_generator.playwright.options import PlaywrightOptions
from md_generator.playwright.pipeline import convert_url_to_md


def zip_directory(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                arc = p.relative_to(root)
                zf.write(p, arc.as_posix())
    return buf.getvalue()


async def _convert_urls_to_artifact(urls: list[str], artifact: Path, options: PlaywrightOptions) -> None:
    if len(urls) == 1:
        await convert_url_to_md(urls[0], artifact, options)
        return
    for i, u in enumerate(urls):
        sub = artifact / f"page-{i}"
        await convert_url_to_md(u, sub, options)


def _run_convert_sync(coro: Coroutine[Any, Any, None]) -> None:
    """Run async conversion without requiring the caller to be on the main asyncio loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return

    import concurrent.futures

    def _in_thread() -> None:
        asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_in_thread).result()


def build_artifact_zip_bytes(
    *,
    url: str | None,
    urls: list[str] | None,
    options: PlaywrightOptions,
) -> bytes:
    """Run Playwright conversion into a temp dir; return ZIP bytes (document.md + assets/)."""
    import tempfile

    targets: list[str]
    if urls:
        targets = list(urls)
    elif url:
        targets = [url.strip()]
    else:
        targets = []

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "artifact"
        out.mkdir(parents=True, exist_ok=True)
        _run_convert_sync(_convert_urls_to_artifact(targets, out, options))
        return zip_directory(out)
